# CLAUDE.md

Claude-specific notes. Read [AGENTS.md](AGENTS.md) first — everything there
applies here too.

## This repo's history with Claude

This repository was built by Claude (Claude Code) working end-to-end: the
backend, frontend, infra, evals, and this documentation set. Three real bugs
were found and fixed only by actually running the stack against a live
local Ollama model rather than trusting mocked tests — see the "Fixed"
section of [CHANGELOG.md](CHANGELOG.md). Keep that habit: when working on
`services/agents/`, `services/patch/`, or `services/llm/`, run the real
integration path (`docker compose up` + a real request, or
`pytest -m integration` with Ollama running) before considering the change
verified, not just the fast mocked suite.

## Things that look unusual on purpose

- `services/agents/graph.py` is a ~60-line hand-rolled graph executor, not
  LangGraph. This was a deliberate choice (see `docs/adr/`), not an
  oversight — don't "fix" it by introducing LangGraph without discussing it.
- `services/retrieval/lexical.py` has two code paths: real Postgres
  `tsvector` full-text search, and a Python term-overlap fallback used only
  because the fast test suite runs against SQLite. Don't remove the
  SQLite path thinking it's dead code — it's what makes the fast tests not
  require a running Postgres.
- `services/agents/diff_extraction.py` has a `_repair_hunk_line_markers`
  function that looks unusually defensive for parsing LLM output. It fixes
  two specific, real failure modes observed against a real small local
  model (markdown-fenced diffs, a hunk's blank context line missing its
  leading-space marker) — see the module's docstring and
  `tests/unit/test_diff_extraction.py` before changing it.
- `app/services/patch/sandbox.py` passes `input=diff_text.encode("utf-8")`
  to `subprocess.run`, not `text=True`. This is not a style choice —
  `text=True` silently corrupts the diff on Windows (LF→CRLF translation on
  stdin). Don't "simplify" it back.

## When asked to add a new LLM-backed workflow

Follow the existing pattern in `services/agents/workflows.py`: retrieve via
`hybrid_retrieve`, build the prompt with `build_context_block`, call the
provider through `_complete_with_metrics` (not directly — that's what wires
up the Prometheus latency/error metrics), resolve citations through
`resolve_citations` (never construct a `Citation` from raw text), and if the
workflow can produce a side-effecting action (like patch proposal does),
make it halt at a persisted, `PENDING_APPROVAL`-style row rather than acting
immediately.
