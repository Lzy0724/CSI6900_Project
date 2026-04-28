import sys
import os
import argparse
import re
import json
import jsonlines
import jpype
import time

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from my_rewriter.config import init_db_config
from my_rewriter.database import DBArgs, Database

parser = argparse.ArgumentParser()
parser.add_argument('--database', type=str, required=True)
parser.add_argument('--logdir', type=str, default='logs_learned_rewrite')
parser.add_argument('--large', action='store_true', required=False, help='whether to execute SQL queries on large database')
parser.add_argument('--cache_db', type=str, default=None, help='sqlite path for learned rewrite cache')
parser.add_argument('--disable_cache', action='store_true', required=False, help='disable learned rewrite cache')
parser.add_argument('--ignore_history', action='store_true', required=False, help='rerun even if name already exists in res.jsonl')
args = parser.parse_args()

pg_config = init_db_config(args.database)
pg_args = DBArgs(pg_config)

from my_rewriter.database import DBArgs, Database
from my_rewriter.rewrite import learned_rewrite
from my_rewriter.db_utils import execute_rewrite
from my_rewriter.my_rewriter.learned_cache import LearnedRewriteCache, extract_sql_features, feature_fingerprint

BUDGET = 20
DATABASE = args.database
LOG_FILENAME = os.path.join(args.logdir, DATABASE, 'res.jsonl')
CACHE_DB_PATH = args.cache_db or os.path.join(args.logdir, DATABASE, 'learned_rewrite_cache.sqlite')

os.makedirs(os.path.dirname(LOG_FILENAME), exist_ok=True)
cache = None if args.disable_cache else LearnedRewriteCache(CACHE_DB_PATH)

history = set()
if os.path.exists(LOG_FILENAME):
    with open(LOG_FILENAME, 'r') as fin:
        for line in fin.readlines():
            obj = json.loads(line)
            history.add(obj['name'])

out_file = jsonlines.open(LOG_FILENAME, "a")
out_file._flush = True

if 'calcite' in DATABASE:
    DATASET = 'calcite'
elif 'tpch' in DATABASE:
    DATASET = 'tpch'
elif 'dsb' in DATABASE:
    DATASET = 'dsb'
else:
    DATASET = DATABASE

schema_path = os.path.join('..', DATASET, 'create_tables.sql')
schema = open(schema_path, 'r').read()

def my_rewrite(query: str, schema: str, name: str) -> dict:
    out_dict = {'name': name}
    create_tables = [x for x in schema.split(';') if x.strip() != '']
    start = time.time()
    features = extract_sql_features(query)
    cache_key = feature_fingerprint(features)
    out_dict['cache_key'] = cache_key
    out_dict['cache_features'] = features

    if cache is not None:
        cached_rule_seq = cache.get(features)
        if cached_rule_seq:
            db = Database(pg_args)
            input_cost = db.cost_estimation(query)
            cached_res = execute_rewrite(query, schema, pg_args, cached_rule_seq, rounds=1)
            out_dict['input_sql'] = query
            out_dict['input_cost'] = float(input_cost)
            out_dict['output_sql'] = str(cached_res['output_sql'])
            out_dict['output_cost'] = float(cached_res['output_cost'])
            out_dict['used_rules'] = [str(r) for r in cached_res['used_rules']]
            out_dict['rewrite_time'] = int((time.time() - start) * 1000)
            out_dict['cache_hit'] = True
            out_dict['llm_invoked'] = False
            return out_dict

    try:
        res = learned_rewrite(query, create_tables, BUDGET, host=pg_config.get('host', 'localhost'), port=str(pg_config.get('port', 5432)), user=pg_config.get('user', 'postgres'), password=pg_config.get('password', 'postgres'), dbname=pg_config.get('dbname', 'postgres'))

        out_dict['input_sql'] = str(res.get("input_sql"))
        out_dict['input_cost'] = float(str(res.get("input_cost")))
        out_dict['output_sql'] = str(res.get("output_sql"))
        out_dict['output_cost'] = float(str(res.get("output_cost")))
        out_dict['used_rules'] = [str(r) for r in res.get("used_rules")]
        out_dict['rewrite_time'] = int(res.get("time"))
        out_dict['cache_hit'] = False
        out_dict['llm_invoked'] = True
        if cache is not None:
            cache.put(features, out_dict['used_rules'])
    except jpype.JException as e:
        out_dict['input_sql'] = query
        db = Database(pg_args)
        out_dict['input_cost'] = db.cost_estimation(query)
        out_dict['output_sql'] = 'None'
        out_dict['output_cost'] = -1
        out_dict['used_rules'] = []
        out_dict['rewrite_time'] = int((time.time() - start) * 1000)
        out_dict['cache_hit'] = False
        out_dict['llm_invoked'] = True
    return out_dict

if DATASET == 'calcite':
    queries_path = os.path.join('..', DATASET, f'{DATASET}.jsonl')
    with open(queries_path, 'r') as fin:
        for line in fin.readlines():
            obj = json.loads(line)
            query = obj['input_sql']
            name = sorted([x['name'] for x in obj['rewrites']])[0]
            if not args.ignore_history and name in history:
                continue
            out_dict = my_rewrite(query, schema, name)
            out_file.write(out_dict)
else:
    queries_path = os.path.join('..', DATASET)

    if os.path.isdir(os.path.join(queries_path, 'queries')):
        queries_path = os.path.join(queries_path, 'queries')

    query_templates = os.listdir(queries_path)
    for template in query_templates:
        if not os.path.isdir(os.path.join(queries_path, template)):
            continue

        max_idx = 1 if args.large else 2
        for idx in range(max_idx):
            query_filename = f'{queries_path}/{template}/{template}_{idx}.sql'
            content = open(query_filename, 'r').read()
            content = re.sub(r'--.*\n', '', content)
            queries = [q.strip() + ';' for q in content.split(';') if q.strip()]
            for j, query in enumerate(queries):
                name = f'{template}_{idx}' if len(queries) == 1 else f'{template}_{idx}_{j}'
                if not args.ignore_history and name in history:
                    continue
                out_dict = my_rewrite(query, schema, name)
                out_file.write(out_dict)
