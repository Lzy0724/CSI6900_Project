# LLM4Rewrite
This repository is your working project version of an LLM-driven SQL rewrite system based on the R-Bot idea, with additional local experimentation for:

- prompt/rule ablation,
- learned cache and ultimate cache pipelines,
- benchmark-oriented analysis scripts,
- visualization outputs for reports.

## Environment

Recommended setup used in this project:

- Python 3.10+
- PostgreSQL (for benchmark execution)
- Java/OpenJDK 17 (for Calcite-based rewrite module)
- Optional virtual environment in `.venv`

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Set your API key before running any LLM rewrite scripts:

```bash
# PowerShell
$env:OPENAI_API_KEY="your_api_key"
```

```bash
# Bash
export OPENAI_API_KEY="your_api_key"
```

## Project Layout

- `my_rewriter/`: main experiment runner and analysis code
- `rag/`: index build and retrieval-side utilities
- `CalciteRewrite/`: Calcite-based rule application module
- `docs/`: generated plots, summaries, and report materials
- `tpch/`, `dsb/`, `calcite/`: benchmark query/schema resources
- `knowledge-base/`: rule summaries and matching helper functions

## Core Run Flows

All major run scripts are in `my_rewriter/`.

### 1) Baseline and prompt/rule workflows

Example:

```bash
cd my_rewriter
python test.py --database tpch --logdir logs_tpch_base --topk 10 --evidence_topk 5 --rule_prune_mode off
python analyze.py --compute_latency --large --database tpch --logdir logs_tpch_base
```

### 2) Learned cache workflows

Example:

```bash
cd my_rewriter
python test_learned_rewrite.py --database dsb --logdir logs_learned_cold --disable_cache --ignore_history
python test_learned_rewrite.py --database dsb --logdir logs_learned_hot --cache_db logs_learned_shared/dsb/cache.sqlite --ignore_history
python analyze_learned_rewrite.py --compute_latency --large --database dsb --logdir logs_learned_hot
```

### 3) Ultimate cache workflows

Example:

```bash
cd my_rewriter
python test_ultimate_rewrite.py --database tpch --logdir logs_ultimate_cold_tpch --cache_db logs_ultimate_shared/tpch/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python test_ultimate_rewrite.py --database tpch --logdir logs_ultimate_hot_tpch --cache_db logs_ultimate_shared/tpch/cache.sqlite --ignore_history --index hybrid --topk 10 --evidence_topk 5 --rule_prune_mode heuristic
python analyze_learned_rewrite.py --compute_latency --large --database tpch --logdir logs_ultimate_hot_tpch
```

## Visualization and Report Outputs

Visualization scripts are under `docs/`:

- `docs/plot_prompt_ablation.py`
- `docs/plot_d3_figures.py`
- `docs/plot_tpch_learned_cache.py`
- `docs/plot_dsb_learned_cache.py`
- `docs/plot_ultimate_cache.py`

Typical usage:

```bash
py -3 docs/plot_prompt_ablation.py
py -3 docs/plot_d3_figures.py
py -3 docs/plot_ultimate_cache.py
```

Generated outputs are saved under:

- `docs/d3_figures/`
- `docs/prompt_ablation_batch/`
- `docs/optimized_before/`
- `docs/optimized_after/`
- `docs/new_batch/`

## Notes for This Repo

- The current branch intentionally avoids pushing large runtime artifacts (for example Chroma DB binaries) as code commits.
- Logs are produced locally in multiple `logs*` directories and may be noisy in working tree status.
- For clean pushes, prefer code/docs-only commits.

## Citation

If you need to cite the original paper concept:

```bibtex
@article{sun2025rbot,
  title={R-Bot: An LLM-based Query Rewrite System},
  author={Zhaoyan Sun, Xuanhe Zhou, Guoliang Li, Xiang Yu, Jianhua Feng, Yong Zhang},
  journal={Proceedings of the VLDB Endowment},
  volume={18},
  number={12},
  pages={5031--5044},
  year={2025},
  publisher={VLDB Endowment}
}
```
