: "${OPENAI_API_KEY:?Please set OPENAI_API_KEY before running this script.}"

python test.py --database tpch --logdir logs_tpch_base --topk 10 --evidence_topk 5 --rule_prune_mode off
python analyze.py --compute_latency --large --database tpch --logdir logs_tpch_base

python test.py --database tpch --logdir logs_tpch_top1 --topk 10 --evidence_topk 1 --rule_prune_mode off
python analyze.py --compute_latency --large --database tpch --logdir logs_tpch_top1

python test.py --database tpch --logdir logs_tpch_prune_top5 --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python analyze.py --compute_latency --large --database tpch --logdir logs_tpch_prune_top5

python test.py --database tpch --logdir logs_tpch_prune_top1 --topk 10 --evidence_topk 1 --rule_prune_mode heuristic
python analyze.py --compute_latency --large --database tpch --logdir logs_tpch_prune_top1

python test_learned_rewrite.py --database tpch --logdir logs_learned_cold --disable_cache --ignore_history
python analyze_learned_rewrite.py --compute_latency --large --database tpch --logdir logs_learned_cold

python test_learned_rewrite.py --database tpch --logdir logs_warmup --cache_db logs_learned_shared/tpch/cache.sqlite --ignore_history
python test_learned_rewrite.py --database tpch --logdir logs_learned_hot --cache_db logs_learned_shared/tpch/cache.sqlite --ignore_history
python analyze_learned_rewrite.py --compute_latency --large --database tpch --logdir logs_learned_hot
