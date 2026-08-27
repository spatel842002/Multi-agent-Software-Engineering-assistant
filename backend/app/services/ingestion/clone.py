from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import UnprocessableIngestionError


class ClonedRepository:
    def __init__(self, path: Path, commit_sha: str) -> None:
        self.path = path
        self.commit_sha = commit_sha


def clone_repository(source_url: str, *, workspace_root: str | None = None) -> ClonedRepository:
    """Shallow-clones `source_url` into an isolated per-job directory under the
    workspace root, bounded by a hard subprocess timeout so a slow/hostile
    remote can't hang an ingestion worker indefinitely.
    """
    settings = get_settings()
    root = Path(workspace_root or settings.workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f"repo-{uuid.uuid4().hex}"

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", source_url, str(dest)],
            check=True,
            capture_output=True,
            timeout=settings.ingestion_clone_timeout_seconds,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise UnprocessableIngestionError(
            f"Clone timed out after {settings.ingestion_clone_timeout_seconds}s."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise UnprocessableIngestionError(f"Clone failed: {exc.stderr.strip()[:500]}") from exc

    total_size_mb = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) / (1024 * 1024)
    if total_size_mb > settings.ingestion_max_repo_size_mb:
        raise UnprocessableIngestionError(
            f"Repository is {total_size_mb:.1f}MB, exceeding the "
            f"{settings.ingestion_max_repo_size_mb}MB limit."
        )

    commit_sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    return ClonedRepository(path=dest, commit_sha=commit_sha)
