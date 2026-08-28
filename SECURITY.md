# Security Policy

## Supported versions

This is a single-branch portfolio project — only `main` is supported.
Security fixes land there directly.

## Reporting a vulnerability

Please report security issues privately rather than via a public GitHub
issue. Use GitHub's private vulnerability reporting
(`Security` tab → `Report a vulnerability`) on this repository, or email the
address listed on [Shriya's portfolio](https://shriya-patel-software-portfolio.vercel.app/).

Include: what you found, how to reproduce it, and the potential impact.
This is a personal project maintained by one person — expect an initial
response within a few days, not an SLA.

## What's in scope

The application code in `backend/` and `frontend/`, the Dockerfiles, and the
`k8s/`/`terraform/` reference infrastructure. Third-party dependencies
should generally be reported upstream, though a report here that a known CVE
affects a pinned version we ship is still useful.

## Security controls already in place

See [docs/security.md](docs/security.md) for the full threat model. In
short: Argon2id password hashing, single-use JWT refresh tokens with reuse
detection (a replayed token revokes its whole chain), SSRF-guarded
repository ingestion (scheme allowlist + private/loopback IP resolution
blocking), owner-scoped authorization (404, not 403, for another user's
resources), rate limiting on auth endpoints, and a human-approval gate that
sits between any LLM-proposed patch and it ever being applied or executed
(and even then, only inside a disposable sandbox copy of the repository,
never the canonical clone).

## Known, documented limitations

- The patch sandbox is process-level isolation (a throwaway directory copy
  plus a subprocess timeout), not a hermetic container/VM sandbox — see
  [docs/security.md](docs/security.md#patch-sandbox-isolation-model) for the
  full reasoning and what a stronger version would require.
- Rate limiting uses in-process storage in the test environment and Redis in
  Docker Compose/production; a multi-instance production deployment should
  confirm the shared Redis-backed limiter is configured (it is, by default,
  outside `ENVIRONMENT=test`).
- No dependency in this project has a known unpatched critical CVE as of the
  last `pip-audit`/`npm audit` run in CI; see the CI job output for the
  current state, not this file (it will go stale).
