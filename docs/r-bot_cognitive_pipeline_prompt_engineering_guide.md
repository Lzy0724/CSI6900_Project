# R-Bot Deterministic Cognitive Pipeline: Prompt Engineering Guide

This document describes how to turn multi-step LLM query rewriting into a reproducible, parseable, and verifiable pipeline.

## Core Principle

Treat the LLM as a **rule orchestrator**, not a free-form SQL generator:
- select candidate rules,
- order them with evidence-backed reasoning,
- let the rewrite engine execute the final transformations.

## Four-Layer Prompt Design

1. **System constraints**
   - strict role boundaries,
   - rule-name allowlist,
   - semantic-equivalence requirement.
2. **State injection**
   - SQL text,
   - schema metadata (DDL, PK/FK/UNIQUE when possible),
   - relevant runtime context.
3. **Evidence anchoring**
   - structured rule specifications (`condition`, `transformation`, `matching function`),
   - retrieved Q&A snippets tied to current SQL.
4. **Stepwise reasoning protocol**
   - diagnosis,
   - rule selection,
   - ordering,
   - engine execution and reflection.

## Implementation Roadmap

- Define a strict JSON schema for every model response.
- Build prompt sections with reusable builders (`system`, `state`, `evidence`) instead of monolithic strings.
- Enforce parser and validator checks:
  - illegal rule names are rejected,
  - malformed output triggers controlled retry.
- Log retrieval metadata (`topk` evidence IDs, query hashes) for reproducibility.

## Validation Criteria

- High parse success rate for structured output.
- 100% rule-name legality within current candidate set.
- Clear evidence traceability for each selected step.
- Final rewritten result must come from the engine output.

## Reporting Guidance

For papers/reports, frame this as protocol-driven systems engineering over open evidence and observable behavior, rather than recovering hidden proprietary prompts.
