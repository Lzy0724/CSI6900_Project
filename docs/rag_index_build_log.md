# RAG Index Build Log

This document records terminal summaries for local `python rag_*.py` runs to support reproducibility, writing, and debugging.

Initial record date: `2026-04-22`.

## Record 1: `rag/rag_gen.py` (main index / `stackoverflow` collection)

| Item | Value |
|------|-------|
| Working directory | `LLM4Rewrite/rag` |
| Command | `python rag_gen.py` |
| Environment | project `.venv` |

Terminal summary:

| Metric | Value |
|--------|-------|
| tqdm pass 1 lines/items | 3798 |
| tqdm pass 2 lines/items | 2091 |
| Q&A Count | 2091 |
| SQL Count | 2910 |
| Node Count | 5507 |

## Record 2: `rag/rag_structure.py` (`stackoverflow_structure` collection)

| Item | Value |
|------|-------|
| Working directory | `LLM4Rewrite/rag` |
| Command | `python rag_structure.py` |
| Environment | project `.venv` |

Terminal summary:

| Metric | Value |
|--------|-------|
| tqdm pass 1 lines/items | 3798 |
| SQL Count | 2216 |
| Node Count | 4724 |

Note: these are two consecutive runs from the same working session. For paper/report usage, add machine info, Python/dependency versions, and model parameters (for example `OPENAI` and `--model`).
