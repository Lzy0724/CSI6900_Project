# New Batch Results Summary

This document summarizes the latest benchmark batch for:
- Prompt ablation
- Learned cache (cold vs hot)
- Ultimate cache (cold vs hot)

## Data Sources

- R-Bot prompt-ablation logs:
  - `logs_* / tpch.log`
  - `logs_* / dsb.log`
- Learned cache logs:
  - `my_rewriter/logs_learned_cold/*.log`
  - `my_rewriter/logs_learned_hot/*.log`
- Ultimate cache logs:
  - `my_rewriter/logs_ultimate_cold_*/**/res.jsonl`
  - `my_rewriter/logs_ultimate_hot_*/**/res.jsonl`

## Plot Scripts

- Prompt ablation:
  - `py -3 docs/plot_prompt_ablation.py`
  - Output: `docs/prompt_ablation_batch/`
- Learned cache:
  - `py -3 docs/plot_tpch_learned_cache.py`
  - `py -3 docs/plot_dsb_learned_cache.py`
- Ultimate cache:
  - `py -3 docs/plot_ultimate_cache.py`
  - Output: `docs/new_batch/`
- D3 supplementary figures:
  - `py -3 docs/plot_d3_figures.py`
  - Output: `docs/d3_figures/`

## Key Observations

- Ultimate cache hot runs substantially reduce rewrite latency compared with cold runs while keeping plan-quality metrics stable.
- Prompt pruning usually improves latency, but quality/latency trade-offs vary by dataset.
- Learned cache shows strong latency reduction on both DSB and TPC-H in hot runs.

## Notes

- If `Average Overall` is `inf` or missing, use `Median Overall` for robust comparison.
- Ensure each run uses the same query set and sample count before drawing final conclusions.
