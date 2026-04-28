: "${OPENAI_API_KEY:?Please set OPENAI_API_KEY before running this script.}"

python test_ultimate_rewrite.py --database dsb --logdir logs_ultimate_cold_dsb --cache_db logs_ultimate_shared/dsb/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python test_ultimate_rewrite.py --database dsb --logdir logs_ultimate_hot_dsb --cache_db logs_ultimate_shared/dsb/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python analyze_learned_rewrite.py --compute_latency --large --database dsb --logdir logs_ultimate_hot_dsb
