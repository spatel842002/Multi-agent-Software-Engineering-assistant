from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "target",
}

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".sh": "shell",
    ".toml": "toml",
}

MAX_SINGLE_FILE_BYTES = 1_000_000  # 1MB: larger files are almost never useful chunk sources


@dataclass(frozen=True)
class DiscoveredFile:
    relative_path: str
    absolute_path: Path
    language: str
    size_bytes: int


def _looks_binary(sample: bytes) -> bool:
    return b"\x00" in sample


def walk_repository_files(root: Path) -> Iterator[DiscoveredFile]:
    """Yields every text source file under `root`, skipping VCS/build/dependency
    directories, binary files, and anything above the per-file size cap.
    """
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in path.relative_to(root).parts):
            continue

        size = path.stat().st_size
        if size == 0 or size > MAX_SINGLE_FILE_BYTES:
            continue

        with path.open("rb") as f:
            sample = f.read(4096)
        if _looks_binary(sample):
            continue

        language = _LANGUAGE_BY_EXTENSION.get(path.suffix.lower(), "text")
        yield DiscoveredFile(
            relative_path=path.relative_to(root).as_posix(),
            absolute_path=path,
            language=language,
            size_bytes=size,
        )
