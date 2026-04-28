# 1. Core method (LLM-R²)
python test.py --database tpch --logdir logs
python analyze.py --compute_latency --database tpch --logdir logs --large

# 2. Pure LLM baseline (LLM Only)
python test_llm_only.py --database tpch --logdir logs_llm_only
python analyze_llm_only.py --compute_latency --database tpch --logdir logs_llm_only --large

# 3. Traditional baseline (Learned Rewrite)
python test_learned_rewrite.py --database tpch --logdir logs_learned_rewrite
python analyze_learned_rewrite.py --compute_latency --database tpch --logdir logs_learned_rewrite --large