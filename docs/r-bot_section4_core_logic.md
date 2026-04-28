# R-Bot Section 4: Core Logic and Rule Source Breakdown

Reference: `2412.01661v2.pdf` (*R-Bot: An LLM-based Query Rewrite System*).  
Scope: Section 4, *Rewrite Evidence Preparation*.

## What Section 4 Does

Section 4 focuses on offline preparation:
- extracting and standardizing rewrite evidence,
- so online rewriting can build better rewrite recipes.

It does **not** implement algebraic rewrites in the optimizer itself.

## Two Evidence Streams

- **4.1 Rewrite rule specifications**
  - source A: optimizer rule code (for example, Calcite rule implementations),
  - source B: database documentation.
- **4.2 Rewrite Q&A pairs**
  - high-quality SQL-related Q&A from community sources.

## Key Clarification: Engine Rules vs LLM Responsibilities

- The query rewrite engine (for example Calcite) provides executable rewrite semantics.
- The LLM in Section 4 is mainly used to:
  - extract structured rule specifications from code/docs,
  - filter and organize high-quality Q&A evidence.
- Online, the LLM helps with rule selection and ordering from candidate sets; the engine still performs actual rewrites.

## Practical Takeaway

Section 4 does not provide a full exhaustive list of all Calcite rules.  
It provides methodology and representative examples (such as those in Table 2 / Figure 3).
