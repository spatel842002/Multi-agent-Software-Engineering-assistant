"""Lexical (keyword) search over ingested chunks.

Production (Postgres) uses a real `tsvector`/`ts_rank` full-text query -- the
GIN-indexed `content_tsv` column added in the Alembic migration
`21b381a63167_chunk_fulltext_index`. Any other SQLAlchemy dialect (only SQLite, and
only in the test suite) falls back to an in-Python term-overlap ranking over
the repository's chunks, since SQLite has no comparable full-text primitive
without a separate FTS5 virtual table. Both paths return the same
`LexicalHit` shape so callers (`hybrid.py`) don't need to know which ran.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Chunk

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


@dataclass(frozen=True)
class LexicalHit:
    chunk_id: uuid.UUID
    score: float


async def lexical_search(
    db: AsyncSession, *, repository_id: uuid.UUID, query: str, top_k: int
) -> list[LexicalHit]:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return await _postgres_fulltext_search(db, repository_id=repository_id, query=query, top_k=top_k)
    return await _python_term_overlap_search(db, repository_id=repository_id, query=query, top_k=top_k)


async def _postgres_fulltext_search(
    db: AsyncSession, *, repository_id: uuid.UUID, query: str, top_k: int
) -> list[LexicalHit]:
    stmt = text(
        """
        SELECT id, ts_rank(content_tsv, plainto_tsquery('english', :query)) AS rank
        FROM chunks
        WHERE repository_id = :repository_id
          AND content_tsv @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :top_k
        """
    )
    rows = (
        await db.execute(stmt, {"query": query, "repository_id": str(repository_id), "top_k": top_k})
    ).all()
    return [LexicalHit(chunk_id=row.id, score=float(row.rank)) for row in rows]


async def _python_term_overlap_search(
    db: AsyncSession, *, repository_id: uuid.UUID, query: str, top_k: int
) -> list[LexicalHit]:
    query_terms = {t.lower() for t in _TOKEN_RE.findall(query)}
    if not query_terms:
        return []

    chunks = (await db.execute(select(Chunk).where(Chunk.repository_id == repository_id))).scalars().all()

    scored: list[LexicalHit] = []
    for chunk in chunks:
        chunk_terms = _TOKEN_RE.findall(chunk.content.lower())
        if not chunk_terms:
            continue
        overlap = sum(1 for t in chunk_terms if t in query_terms)
        if overlap == 0:
            continue
        # Simple TF-style score, normalized by chunk length so long chunks don't
        # win purely on volume.
        score = overlap / len(chunk_terms)
        scored.append(LexicalHit(chunk_id=chunk.id, score=score))

    scored.sort(key=lambda h: h.score, reverse=True)
    return scored[:top_k]
