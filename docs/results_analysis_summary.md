# Learned Rewrite Cache Analysis (DSB + TPC-H)

## Summary

- This optimization (caching Query Template -> Rule Sequence) significantly reduces rewrite-stage latency on **DSB and TPC-H**.
- The gain mainly comes from **latency and cost**, not from plan-quality (`Improved X out of Y`) improvement.
- Results show the core hot-start goal is achieved: skipping most LLM inference when cache hits.

## DSB Results

### Pre-optimization method comparison (`docs/optimized_before/dsb_metrics_summary.json`)

- `R-Bot`: `improved_pct=28.95%`, `avg_total_time_ms=39930.46`, `median_overall_ms=38733.18`
- `LLM-Only`: `improved_pct=0.00%`, `avg_total_time_ms=7491.92`, `median_overall_ms=7014.03`
- `LearnedRewrite`: `improved_pct=0.00%`, `avg_total_time_ms=3956.42`, `median_overall_ms=2757.02`

Conclusion: on this DSB query batch, `LearnedRewrite` has better median end-to-end latency than `LLM-Only` and `R-Bot`.

### Cache before/after comparison (`docs/optimized_after/dsb_learned_cache_summary.json`)

- `cache_hit_rate`: **84.21%**
- `avg_total_time_ms`: `4707.97 -> 1183.53` (about **-74.86%**)
- `avg_overall_ms`: `4708.03 -> 1183.59` (about **-74.86%**)
- `rewrite_time_improvement_ratio`: **94.62%**

Conclusion: once cache hits on DSB, latency drops substantially in both end-to-end and rewrite-specific metrics.

## TPC-H Results

### Pre-optimization method comparison (`docs/optimized_before/tpch_metrics_summary.json`)

- `R-Bot`: `improved_pct=45.00%`, `avg_total_time_ms=34190.63`, `median_overall_ms=52041.89`
- `LLM-Only`: `improved_pct=13.64%`, `avg_total_time_ms=6487.55`, `median_overall_ms=23890.61`
- `LearnedRewrite`: `improved_pct=18.18%`, `avg_total_time_ms=1482.82`, `median_overall_ms=23808.43`

Conclusion: on TPC-H, `LearnedRewrite` is stronger in total latency while `R-Bot` has a higher improved ratio.

### Cache before/after comparison (`docs/optimized_after/tpch_learned_cache_summary.json`)

- `cache_hit_rate`: **90.91%**
- `avg_total_time_ms`: `1117.59 -> 300.18` (about **-73.14%**)
- `rewrite_time_improvement_ratio`: **88.57%**
- `avg_overall_ms`: currently `null` in logs, so end-to-end average reduction cannot be computed directly

Conclusion: cache also significantly reduces rewrite-stage latency on TPC-H; end-to-end reduction requires complete `Average Overall` logs.

## About the "Plan Quality" Metric

- DSB `improved_pct` is `0.0%` both before and after cache (`0/38`).
- TPC-H `improved_pct` changes from `22.73%` to `18.18%`.

Explanation: cache primarily reuses existing rule sequences and skips inference; it targets latency reduction, not guaranteed quality gains. Current results match that expectation: **large latency improvement, limited quality change**.

## Next Steps

- Use the same query set and identical `total` size across runs (TPC-H currently mixes `20` and `22`).
- Ensure `analyze_* --large` produces complete `Average Overall` metrics for fair end-to-end comparison.
- In reports, position cache work as a systems optimization (latency/cost), separate from rule-quality optimization (plan quality).
