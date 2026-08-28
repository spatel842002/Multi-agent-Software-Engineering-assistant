# ADR 0001: Hybrid lexical + dense retrieval, fused with Reciprocal Rank Fusion

## Status

Accepted.

## Context

Code search has two failure modes if you pick only one retrieval strategy:

- **Dense-only (embeddings)**: strong for paraphrased/semantic questions
  ("how does auth work"), weak for exact-identifier lookups — an embedding
  model doesn't reliably place `validate_source_url` near its own call
  sites just because they share a token.
- **Lexical-only (full-text)**: strong for exact identifiers, weak for
  semantic questions phrased differently from the code's own vocabulary.

Combining both requires fusing two rankers whose scores live on
incomparable scales: cosine similarity (dense) and `ts_rank` (lexical,
Postgres-specific, not even comparable across queries).

## Decision

Run both rankers independently (`services/retrieval/lexical.py`,
Qdrant search in `services/retrieval/vector_store.py`), then fuse by
**Reciprocal Rank Fusion**: `score(d) = sum over rankers r of 1/(k + rank_r(d))`,
using only each ranker's rank *position*, never its raw score. `k=60`, the
commonly-cited default from the original RRF paper (Cormack et al.).

See `services/retrieval/hybrid.py`.

## Consequences

- No score-normalization logic to get subtly wrong.
- A chunk that's a strong RESULT in either ranker (even if weak in the
  other) still surfaces near the top — the fusion is closer to a max than
  an average.
- Lexical search has two implementations: real Postgres `tsvector`/`ts_rank`
  in production, and a Python term-overlap fallback for the SQLite-backed
  fast test suite (see ADR 0002). Retrieval-quality *numbers* differ
  between the two paths; that's expected and doesn't affect the fusion
  logic itself, which only depends on rank order.
