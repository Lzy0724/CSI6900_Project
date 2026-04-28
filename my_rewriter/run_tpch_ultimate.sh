: "${OPENAI_API_KEY:?Please set OPENAI_API_KEY before running this script.}"

python test_ultimate_rewrite.py --database tpch --logdir logs_ultimate_cold_tpch --cache_db logs_ultimate_shared/tpch/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python test_ultimate_rewrite.py --database tpch --logdir logs_ultimate_hot_tpch --cache_db logs_ultimate_shared/tpch/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python analyze_learned_rewrite.py --compute_latency --large --database tpch --logdir logs_ultimate_hot_tpch
