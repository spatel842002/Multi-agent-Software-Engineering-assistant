"""Applies an approved diff and runs its validation command against an
isolated *copy* of the repository, never the canonical clone the retrieval
index was built from -- so a patch run can't silently desynchronize search
results from what's actually on disk.

Isolation model (documented honestly, see `docs/security.md`): this is
process-level isolation -- a throwaway directory copy plus a hard subprocess
timeout -- not a hermetic containerized sandbox (no network namespace
isolation, no seccomp/gVisor). That stronger isolation is a documented,
deferred hardening item, not something this code claims to provide.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


@dataclass(frozen=True)
class SandboxRunResult:
    apply_succeeded: bool
    apply_output: str
    test_ran: bool
    test_succeeded: bool
    test_output: str


def _make_sandbox_copy(source_repo_path: Path) -> Path:
    settings = get_settings()
    root = Path(settings.workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"sandbox-{uuid.uuid4().hex}"
    shutil.copytree(source_repo_path, dest, ignore=shutil.ignore_patterns(".git"))
    return dest


def run_patch_in_sandbox(
    *, source_repo_path: Path, diff_text: str, test_command: str | None
) -> SandboxRunResult:
    """Copies the repo, applies `diff_text` with `git apply` in the copy, and
    (if the apply succeeded and a test command was proposed) runs it there
    with a hard timeout. Never touches `source_repo_path` itself.
    """
    settings = get_settings()
    sandbox_dir = _make_sandbox_copy(source_repo_path)

    apply_result = subprocess.run(
        ["git", "apply", "--verbose"],
        # `input=` as bytes, not `text=True` with a str: subprocess's text
        # mode applies universal-newline translation to stdin on Windows,
        # silently rewriting LF to CRLF before git ever sees it -- which
        # desyncs a unified diff's hunk from the (LF) file it targets and
        # makes `git apply` reject an otherwise-perfectly-valid patch with
        # "corrupt patch". Confirmed directly: a `difflib`-generated diff,
        # byte-identical in Python, failed to apply until this was bytes-mode.
        input=diff_text.encode("utf-8"),
        cwd=sandbox_dir,
        capture_output=True,
        timeout=30,
    )
    apply_succeeded = apply_result.returncode == 0
    apply_output = apply_result.stdout.decode("utf-8", errors="replace") + apply_result.stderr.decode(
        "utf-8", errors="replace"
    )

    if not apply_succeeded or not test_command:
        return SandboxRunResult(
            apply_succeeded=apply_succeeded,
            apply_output=apply_output,
            test_ran=False,
            test_succeeded=False,
            test_output="",
        )

    try:
        test_result = subprocess.run(
            test_command,
            shell=True,  # noqa: S602 - command originates from an LLM proposal a human explicitly approved, run only inside the disposable sandbox copy
            cwd=sandbox_dir,
            capture_output=True,
            text=True,
            timeout=settings.patch_sandbox_timeout_seconds,
        )
        return SandboxRunResult(
            apply_succeeded=True,
            apply_output=apply_output,
            test_ran=True,
            test_succeeded=test_result.returncode == 0,
            test_output=(test_result.stdout or "") + (test_result.stderr or ""),
        )
    except subprocess.TimeoutExpired:
        return SandboxRunResult(
            apply_succeeded=True,
            apply_output=apply_output,
            test_ran=True,
            test_succeeded=False,
            test_output=f"Test command timed out after {settings.patch_sandbox_timeout_seconds}s.",
        )
