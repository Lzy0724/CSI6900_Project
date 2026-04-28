# Test DSB with consistent analysis settings across methods.
# Use --large so all analyzers report Overall latency metrics comparably.
: "${OPENAI_API_KEY:?Please set OPENAI_API_KEY before running this script.}"

python test.py --database dsb --logdir logs
python analyze.py --compute_latency --large --database dsb --logdir logs

python test_llm_only.py --database dsb --logdir logs_llm_only
python analyze_llm_only.py --compute_latency --large --database dsb --logdir logs_llm_only

python test_learned_rewrite.py --database dsb --logdir logs_learned_rewrite
python analyze_learned_rewrite.py --compute_latency --large --database dsb --logdir logs_learned_rewrite

python test_learned_rewrite.py --database dsb --logdir logs_learned_cold --disable_cache
python analyze_learned_rewrite.py --compute_latency --large --database dsb --logdir logs_learned_cold

python test_learned_rewrite.py --database dsb --logdir logs_warmup --cache_db logs_learned_shared/dsb/cache.sqlite --ignore_history
python test_learned_rewrite.py --database dsb --logdir logs_learned_hot --cache_db logs_learned_shared/dsb/cache.sqlite --ignore_history
python analyze_learned_rewrite.py --compute_latency --large --database dsb --logdir logs_learned_hot
