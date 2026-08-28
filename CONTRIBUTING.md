# Contributing

This is a personal portfolio project, but it's built to a standard where
real contributions are welcome.

## Getting set up

See [docs/local-development.md](docs/local-development.md) for the full
local setup (Docker Compose, running backend/frontend outside Docker,
pulling the local Ollama models).

## Before opening a PR

Backend:

```bash
cd backend
ruff format app tests
ruff check app tests
mypy app
pytest --cov
```

Frontend:

```bash
cd frontend
npm run lint
npm run format
npm test
npm run build
```

Infra (if you touched `terraform/eks/` or `k8s/`):

```bash
cd terraform/eks && terraform fmt -recursive && terraform validate
```

All of the above run in CI (`.github/workflows/ci.yml`) and must pass.

## Commit style

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`,
`fix:`, `test:`, `docs:`, `chore:`, `refactor:`. Keep the subject line under
~70 characters; explain *why* in the body when it's not obvious from the
diff alone.

## Truthfulness

Don't describe a feature as working unless you've actually run it and have
evidence (a passing test, a real command output). Don't fabricate
benchmarks, screenshots, or eval results — see [docs/testing.md](docs/testing.md)
for how the eval suite (`evals/`) is meant to be reproduced, not just
described.

## Reporting bugs / security issues

Functional bugs: open a GitHub issue. Security issues: see
[SECURITY.md](SECURITY.md) — do not open a public issue for those.
