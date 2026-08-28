# Licenses and attribution

See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for the full
dependency license table. This page covers non-code attribution.

## Code

All application code in this repository (`backend/app/`, `frontend/src/`,
`evals/`, infra config) is original work written for this project, licensed
[MIT](../LICENSE).

## Data

- `backend/tests/fixtures/sample_repo/` — a small fixture Python module,
  written from scratch for this project's test suite. Not derived from any
  external source; MIT-licensed along with the rest of this repo.
- The evaluation golden set (`evals/golden_dataset.py`) is hand-written
  against that same fixture repo.
- No external dataset is bundled with this project.

## Repositories ingested during development/demo

Real end-to-end verification during development ingested two small, public,
appropriately-licensed repositories via their public `https://` clone URLs
(never committed to this repository — only their derived index rows/chunks
existed transiently in a local database, and the raw API-response evidence
committed under `docs/assets/screenshots/` quotes small excerpts of their
public README/config content as part of demonstrating a real answer):

- [`pypa/sampleproject`](https://github.com/pypa/sampleproject) — MIT
  License, maintained by the Python Packaging Authority as an official
  example project.
- [`octocat/Hello-World`](https://github.com/octocat/Hello-World) — GitHub's
  own public test/demo repository.

## Models

`qwen2.5-coder:1.5b` and `nomic-embed-text`, both pulled at runtime via
`ollama pull` (not committed to this repository) and both Apache-2.0
licensed — see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md#models).

## Media / screenshots

Every image under [docs/assets/screenshots/](assets/screenshots/) is a real
screenshot captured by this project's own Playwright e2e test
(`frontend/e2e/smoke.spec.ts`) against the running application, or a real
API response transcript — none are stock imagery, mockups, or AI-generated
UI. No third-party image assets are used anywhere in this project (the
frontend ships no logo/icon beyond the browser's default favicon).
