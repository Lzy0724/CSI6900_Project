import logging
import sys
from typing import Any, Dict, List, Optional, Sequence, Union, cast, Tuple
import typing as t
from collections import defaultdict
import json
import itertools

import chromadb
from llama_index.core import VectorStoreIndex, StorageContext, Settings
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.core.async_utils import run_async_tasks
from llama_index.core.schema import (
    BaseNode,
    TextNode,
    NodeWithScore
)
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.retrievers import BaseRetriever

from rag.my_query_fusion_retriver import MyQueryFusionRetriever, FUSION_MODES
from rag.prompts import STACKOVERFLOW_QA_PROMPT
from rag.gen_rewrites_from_rules import calcite_rules
from my_rewriter.database import DBArgs
from my_rewriter.my_utils import MyModel
from my_rewriter.db_utils import execute_rewrite
from my_rewriter.my_rewriter.rule_prune import prune_rules_for_query


def rag_rewrite(
    retriever_res: t.List[NodeWithScore],
    rewrites: t.List[t.Dict],
    query: str,
    schema: str,
    db_args: DBArgs,
    model_args: t.Dict[str, str],
    CASE_BATCH: int = 5,
    RULE_BATCH: int = 10,
    REWRITE_ROUNDS: int = 1,
    EVIDENCE_TOP_K: t.Optional[int] = None,
    RULE_PRUNE_MODE: str = "off",
    MAX_RULE_CANDIDATES: t.Optional[int] = None,
):
    model = MyModel(model_args)
    if EVIDENCE_TOP_K is not None and EVIDENCE_TOP_K > 0:
        retriever_res = retriever_res[:EVIDENCE_TOP_K]
    logging.info(f'Prompt Controls: {{"evidence_top_k": {EVIDENCE_TOP_K}, "rule_prune_mode": "{RULE_PRUNE_MODE}", "max_rule_candidates": {MAX_RULE_CANDIDATES}}}')

    nl_suggestions = [obj['rewrite'] for obj in rewrites['nl']]
    normal_rules = [r for r in rewrites['calcite'] if r['type'] == 'normal']
    explore_rules = [r for r in rewrites['calcite'] if r['type'] == 'explore']
    if RULE_PRUNE_MODE == "heuristic":
        before_normal, before_explore = len(normal_rules), len(explore_rules)
        normal_rules = prune_rules_for_query(query, normal_rules)
        explore_rules = prune_rules_for_query(query, explore_rules)
        logging.info(
            f"Rule Pruning: normal {before_normal}->{len(normal_rules)}, explore {before_explore}->{len(explore_rules)}"
        )
    normal_suggestions = [obj['rewrite'] for obj in normal_rules]
    strategies = normal_suggestions + nl_suggestions

    tasks = []
    tasks.append(model.gen_summarize_strategies(query, retriever_res, strategies, case_batch=CASE_BATCH))
    tasks.append(model.select_rules_from_cases(retriever_res, normal_rules=normal_rules, explore_rules=explore_rules))
    task_results = run_async_tasks(tasks)
    summarized_strategies = task_results[0]
    selected_rules: t.List[t.List[t.Dict[str, str]]] = task_results[1]

    suggestions_str = '\n\n'.join([f'### Suggestion {i+1}:\n"""{s}"""' for i, s in enumerate(summarized_strategies)])
    logging.info('Intermediate Results: ' + str({'suggestions_str': suggestions_str, 'selected_rules': selected_rules}))
    logging.info('Start recipe-based rewrite...')

    relevant_rules: t.List[t.Dict[str, str]] = []
    selected_rules_lst: t.List[t.Dict[str, str]] = list(itertools.chain.from_iterable(selected_rules))
    if MAX_RULE_CANDIDATES is not None and MAX_RULE_CANDIDATES > 0:
        selected_rules_lst = selected_rules_lst[:MAX_RULE_CANDIDATES]
        logging.info(f"Rule Candidate Cap Applied: {len(selected_rules_lst)}")
    for i in range((len(selected_rules_lst) - 1) // RULE_BATCH + 1):
        start_idx = i * RULE_BATCH
        end_idx = min((i + 1) * RULE_BATCH, len(selected_rules_lst))
        relevant_rules = model.select_rules(query, suggestions_str, relevant_rules + selected_rules_lst[start_idx:end_idx])
        relevant_rules_str = [obj['name'] for obj in relevant_rules]
        logging.info(f'Rules After the {i + 1}th Selection: {relevant_rules_str}')

    arranged_rule_seq = model.arrange_rules(query, suggestions_str, relevant_rules)
    logging.info(f'Arranged Rule Sequence: {arranged_rule_seq}')

    rewrite_res = execute_rewrite(query, schema, db_args, arranged_rule_seq, REWRITE_ROUNDS)
    used_rules = rewrite_res['used_rules']

    rearranged_rule_seq = model.rearrange_rules(query, suggestions_str, relevant_rules, arranged_rule_seq, used_rules)
    logging.info(f'Rearranged Rule Sequence: {rearranged_rule_seq}')
    rewrite_res = execute_rewrite(query, schema, db_args, rearranged_rule_seq, REWRITE_ROUNDS)
    return {
        "rearranged_rule_seq": [str(x) for x in rearranged_rule_seq],
        "last_rewrite": rewrite_res,
    }
