# ADR 0003: Process-level sandbox isolation for patch execution (not containerized)

## Status

Accepted, with a documented follow-up.

## Context

An approved patch proposal needs its diff applied and its proposed test
command run somewhere. The LLM that generated the diff is untrusted input
in the same sense any generated code is: it should never run against the
canonical ingested clone, and ideally should run with strong isolation
(no network, no access to other repositories' data, bounded resources).

Full isolation (a fresh container or microVM per patch run, no network
namespace, seccomp profile, cgroup limits) is the "correct" answer for a
production system that runs untrusted, LLM-generated shell commands
regularly. It is also a meaningfully larger engineering effort (container
orchestration from within the API/worker process, image management,
cleanup on crash) than this vertical slice's scope justifies right now.

## Decision

`services/patch/sandbox.py` implements **process-level isolation**:

1. `shutil.copytree` the source repository into a disposable directory
   under `WORKSPACE_ROOT` (excluding `.git`) — never touches the canonical
   ingested clone.
2. `git apply` the diff there, as bytes (not `text=True` — see the note in
   `AGENTS.md` about the Windows CRLF bug this avoided).
3. If it applies, run the proposed test command there with `shell=True` and
   a hard subprocess timeout (`PATCH_SANDBOX_TIMEOUT_SECONDS`).
4. The disposable directory is not cleaned up automatically after a run in
   this version — see the follow-up below.

This is documented as exactly what it is in `sandbox.py`'s module docstring
and in `docs/security.md`, not oversold as a hermetic sandbox.

## Consequences

- No network isolation: the test command, if it makes network calls, can
  reach the internet from wherever the backend/worker container runs.
- No resource limits beyond the timeout: a test command that spawns
  many processes or allocates large memory is only bounded by the
  container's own limits, not per-run limits.
- This is acceptable **only** because the whole path is behind a human
  approval gate (`decide_patch_proposal`) — an unapproved proposal never
  reaches this code at all, and every approval is attributed to a specific
  authenticated user via `ApprovalEvent`.

## Follow-up (not done, tracked honestly)

Before running this against genuinely untrusted, high-volume, or
public-facing patch proposals, add: a dedicated ephemeral container per
sandbox run (Docker-in-Docker or a sidecar sandbox service), a network
policy denying egress by default, and disk/CPU/memory cgroup limits. None
of this is implemented; `docs/account-activation-checklist.md` and
`docs/security.md` call it out as a deferred hardening item rather than
letting it go unmentioned.
