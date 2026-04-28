import logging
import sys
import os
import argparse
import re
import json

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from my_rewriter.config import init_llms, init_db_config

parser = argparse.ArgumentParser()
parser.add_argument('--database', type=str, required=True)
parser.add_argument('--logdir', type=str, default='logs')
parser.add_argument('--index', type=str, default='hybrid')
parser.add_argument('--topk', type=int, default=10)
parser.add_argument('--evidence_topk', type=int, default=None, help='limit evidence items included in prompt')
parser.add_argument('--rule_prune_mode', type=str, default='off', choices=['off', 'heuristic'])
parser.add_argument('--max_rule_candidates', type=int, default=None, help='cap candidate rule count in prompt')
args = parser.parse_args()

model_args = init_llms(args.logdir)
pg_config = init_db_config(args.database)

from my_rewriter.database import DBArgs, Database
from my_rewriter.test_utils import test
from my_rewriter.rag_retrieve import init_docstore

RETRIEVER_TOP_K = args.topk
CASE_BATCH = 5
RULE_BATCH = 10
REWRITE_ROUNDS = 1
DATABASE = args.database

if 'calcite' in DATABASE:
    DATASET = 'calcite'
elif 'tpch' in DATABASE:
    DATASET = 'tpch'
elif 'dsb' in DATABASE:
    DATASET = 'dsb'
elif 'hbom' in DATABASE:
    DATASET = 'hbom'
else:
    DATASET = DATABASE

LOG_DIR = os.path.join(project_root, args.logdir, DATASET)
os.makedirs(LOG_DIR, exist_ok=True)

pg_args = DBArgs(pg_config)

schema_path = os.path.join(project_root, DATASET, 'create_tables.sql')
if not os.path.exists(schema_path):
    print(f"Error: schema file not found: {schema_path}")
    exit(1)
schema = open(schema_path, 'r', encoding='utf-8').read()

docstore = init_docstore()

if DATASET == 'calcite':
    queries_path = os.path.join(project_root, DATASET, f'{DATASET}.jsonl')
    with open(queries_path, 'r', encoding='utf-8') as fin:
        for line in fin.readlines():
            obj = json.loads(line)
            query = obj['input_sql']
            name = sorted([x['name'] for x in obj['rewrites']])[0]
            test(name, query, schema, pg_args, model_args, docstore, LOG_DIR, RETRIEVER_TOP_K=RETRIEVER_TOP_K,
                 CASE_BATCH=CASE_BATCH, RULE_BATCH=RULE_BATCH, REWRITE_ROUNDS=REWRITE_ROUNDS, index=args.index,
                 EVIDENCE_TOP_K=args.evidence_topk, RULE_PRUNE_MODE=args.rule_prune_mode,
                 MAX_RULE_CANDIDATES=args.max_rule_candidates)
elif DATASET == 'hbom':
    queries_filename = os.path.join(project_root, DATASET, 'queries.sql')
    content = open(queries_filename, 'r', encoding='utf-8').read()
    queries = [q.strip() + ';' for q in content.split(';') if q.strip()]
    for j, query in enumerate(queries):
        name = f'query{j}'
        test(name, query, schema, pg_args, model_args, docstore, LOG_DIR, RETRIEVER_TOP_K=RETRIEVER_TOP_K,
             CASE_BATCH=CASE_BATCH, RULE_BATCH=RULE_BATCH, REWRITE_ROUNDS=REWRITE_ROUNDS, index=args.index,
             EVIDENCE_TOP_K=args.evidence_topk, RULE_PRUNE_MODE=args.rule_prune_mode,
             MAX_RULE_CANDIDATES=args.max_rule_candidates)
else:
    queries_path = os.path.join(project_root, DATASET, 'queries')
    if not os.path.exists(queries_path):
        queries_path = os.path.join(project_root, DATASET)

    if not os.path.exists(queries_path):
        print(f"Error: query directory not found: {queries_path}")
        exit(1)

    query_templates = os.listdir(queries_path)
    query_templates = [t for t in query_templates if os.path.isdir(os.path.join(queries_path, t))]

    for template in query_templates:
        for idx in range(2):
            query_filename = os.path.join(queries_path, template, f'{template}_{idx}.sql')
            if not os.path.exists(query_filename):
                continue

            content = open(query_filename, 'r', encoding='utf-8').read()
            content = re.sub(r'--.*\n', '', content)
            queries = [q.strip() + ';' for q in content.split(';') if q.strip()]
            for j, query in enumerate(queries):
                name = f'{template}_{idx}' if len(queries) == 1 else f'{template}_{idx}_{j}'
                test(name, query, schema, pg_args, model_args, docstore, LOG_DIR, RETRIEVER_TOP_K=RETRIEVER_TOP_K,
                     CASE_BATCH=CASE_BATCH, RULE_BATCH=RULE_BATCH, REWRITE_ROUNDS=REWRITE_ROUNDS, index=args.index,
                     EVIDENCE_TOP_K=args.evidence_topk, RULE_PRUNE_MODE=args.rule_prune_mode,
                     MAX_RULE_CANDIDATES=args.max_rule_candidates)