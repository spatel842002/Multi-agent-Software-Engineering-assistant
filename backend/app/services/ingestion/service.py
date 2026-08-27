"""Orchestrates repository ingestion: clone -> walk files -> extract symbols
(Python) -> chunk -> persist rows -> embed chunks -> upsert into the vector
store. Deliberately split into `index_repository_files` (operates on an
already-on-disk tree) and `ingest_repository` (adds validation + clone), so
tests can exercise the indexing pipeline against a local fixture directory
without a network clone.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableIngestionError
from app.models.repository import Chunk, IngestedFile, Repository, RepositoryStatus, Symbol, SymbolKind
from app.services.ingestion.chunking import chunk_file_content
from app.services.ingestion.clone import clone_repository
from app.services.ingestion.python_symbols import extract_python_symbols
from app.services.ingestion.security import validate_source_url
from app.services.ingestion.walker import walk_repository_files
from app.services.retrieval.ports import EmbeddingProvider, VectorStore


@dataclass(frozen=True)
class IndexResult:
    file_count: int
    symbol_count: int
    chunk_count: int


def _module_qualified_prefix(relative_path: str) -> str:
    without_ext = relative_path.rsplit(".", 1)[0]
    return without_ext.replace("/", ".").replace("\\", ".")


async def index_repository_files(
    db: AsyncSession,
    *,
    repository: Repository,
    root_path: Path,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
) -> IndexResult:
    file_count = symbol_count = chunk_count = 0

    for discovered in walk_repository_files(root_path):
        content = discovered.absolute_path.read_text(encoding="utf-8", errors="ignore")

        file_row = IngestedFile(
            repository_id=repository.id,
            path=discovered.relative_path,
            language=discovered.language,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            size_bytes=discovered.size_bytes,
        )
        db.add(file_row)
        await db.flush()
        file_count += 1

        if discovered.language == "python":
            for extracted in extract_python_symbols(
                content, module_qualified_prefix=_module_qualified_prefix(discovered.relative_path)
            ):
                db.add(
                    Symbol(
                        file_id=file_row.id,
                        repository_id=repository.id,
                        kind=SymbolKind(extracted.kind),
                        name=extracted.name,
                        qualified_name=extracted.qualified_name,
                        start_line=extracted.start_line,
                        end_line=extracted.end_line,
                        docstring=extracted.docstring,
                    )
                )
                symbol_count += 1

        chunks = chunk_file_content(content, language=discovered.language)
        chunk_rows = [
            Chunk(
                repository_id=repository.id,
                file_id=file_row.id,
                symbol_id=None,
                file_path=discovered.relative_path,
                content=c.content,
                start_line=c.start_line,
                end_line=c.end_line,
                content_hash=hashlib.sha256(c.content.encode("utf-8")).hexdigest(),
            )
            for c in chunks
        ]
        db.add_all(chunk_rows)
        await db.flush()
        chunk_count += len(chunk_rows)

        if chunk_rows:
            vectors = await embedder.embed_documents([c.content for c in chunk_rows])
            await vector_store.upsert_chunks(
                repository_id=repository.id,
                chunk_ids=[c.id for c in chunk_rows],
                vectors=vectors,
            )

    return IndexResult(file_count=file_count, symbol_count=symbol_count, chunk_count=chunk_count)


async def ingest_repository(
    db: AsyncSession,
    *,
    repository: Repository,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    allow_private_hosts: bool = False,
) -> Repository:
    """Runs the full pipeline for `repository` (already persisted with status
    PENDING) and updates its status in place. Never raises on ingestion
    failure -- the repository is marked FAILED with `status_detail` set, so a
    background worker calling this doesn't need special-case error handling.
    """
    try:
        validate_source_url(repository.source_url, allow_private_hosts=allow_private_hosts)

        repository.status = RepositoryStatus.CLONING
        await db.commit()

        cloned = clone_repository(repository.source_url)
        repository.local_path = str(cloned.path)
        repository.commit_sha = cloned.commit_sha
        repository.status = RepositoryStatus.INDEXING
        await db.commit()

        result = await index_repository_files(
            db, repository=repository, root_path=cloned.path, embedder=embedder, vector_store=vector_store
        )
        repository.file_count = result.file_count
        repository.symbol_count = result.symbol_count
        repository.chunk_count = result.chunk_count
        repository.status = RepositoryStatus.READY
        repository.status_detail = None
    except UnprocessableIngestionError as exc:
        repository.status = RepositoryStatus.FAILED
        repository.status_detail = exc.message
    except Exception as exc:  # noqa: BLE001 - any unexpected failure must still land as FAILED, not a crash
        repository.status = RepositoryStatus.FAILED
        repository.status_detail = f"Unexpected ingestion error: {exc}"

    await db.commit()
    await db.refresh(repository)
    return repository
