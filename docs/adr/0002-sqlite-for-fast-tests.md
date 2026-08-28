# ADR 0002: SQLite (file-backed) for the fast test suite, Postgres only for full-text search

## Status

Accepted.

## Context

The application's canonical database is PostgreSQL, and one feature
(`services/retrieval/lexical.py`'s full-text search) genuinely requires a
Postgres-only feature (`tsvector`/`ts_rank`/GIN index — see the migration
`21b381a63167_chunk_fulltext_index`). Requiring a running Postgres for
every test run would make the fast unit/contract suite slow to start and
impossible to run offline/in a minimal CI runner without a services
container.

A second, sharper problem surfaced during implementation: SQLite's
`:memory:` mode is private to the single connection that created it. Any
code that opens its **own** database engine — notably the Celery task
wrapper, which must open its own engine to accurately mirror how a real
worker process (a separate OS process from the API) behaves — would see an
empty, tableless database when the test fixture also used `:memory:`.

## Decision

- The fast test suite (`tests/unit/`, `tests/contract/`, most of
  `tests/integration/`) runs against a **file-backed** temporary SQLite
  database (`tests/conftest.py`'s `db_engine` fixture), not `:memory:`, so
  any code under test that opens its own engine sees the same data.
- `lexical_search()` branches on `db.bind.dialect.name`: real
  `tsvector`/`ts_rank` SQL on Postgres, a Python term-overlap ranking on any
  other dialect (i.e. only ever exercised by SQLite, only in tests).
- A small number of tests are explicitly marked `@pytest.mark.integration`
  and require a real Postgres/Redis/Qdrant/Ollama; these are not part of
  the default `pytest` run (see `pyproject.toml`'s markers and
  `docs/testing.md`).

## Consequences

- The fast suite genuinely runs offline, in seconds, in any CI runner with
  Python and no services.
- The SQLite lexical-search fallback is real code, not a stub — but it is
  **not** the production search implementation, and its ranking numbers
  will differ from Postgres `ts_rank`. This is intentional: the tests
  verify the *fusion and citation-resolution logic* against it, not
  Postgres-specific ranking quality.
- Anyone changing `lexical_search()` must keep both branches returning the
  same `LexicalHit` shape, or `hybrid_retrieve()` breaks silently between
  test and production environments.
