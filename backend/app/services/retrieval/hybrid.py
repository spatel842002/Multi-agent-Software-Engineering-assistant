"""Hybrid retrieval: fuses lexical (keyword) and dense (embedding) search
results with Reciprocal Rank Fusion (RRF), a fusion method that only needs
each ranker's *rank order*, not comparable score scales -- which matters here
because lexical scores (TF/ts_rank) and cosine similarity live on completely
different numeric ranges.

RRF score for a document d: sum over rankers r of 1 / (k + rank_r(d)),
where rank_r(d) is d's 1-indexed position in ranker r's result list (or the
term is omitted if d didn't appear in that ranker's results at all).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telemetry import RETRIEVAL_LATENCY_SECONDS
from app.models.repository import Chunk
from app.services.retrieval.lexical import lexical_search
from app.services.retrieval.ports import EmbeddingProvider, VectorStore

RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    fused_score: float
    lexical_rank: int | None
    dense_rank: int | None


async def hybrid_retrieve(
    db: AsyncSession,
    *,
    repository_id: uuid.UUID,
    query: str,
    embedder: EmbeddingProvider,
    vector_store: VectorStore,
    top_k: int = 8,
    candidate_pool: int = 25,
) -> list[RetrievedChunk]:
    start = time.perf_counter()
    try:
        lexical_hits = await lexical_search(
            db, repository_id=repository_id, query=query, top_k=candidate_pool
        )

        query_vector = await embedder.embed_query(query)
        dense_hits = await vector_store.search(
            repository_id=repository_id, query_vector=query_vector, top_k=candidate_pool
        )
    finally:
        RETRIEVAL_LATENCY_SECONDS.labels(retrieval_mode="hybrid").observe(time.perf_counter() - start)

    lexical_rank = {hit.chunk_id: i + 1 for i, hit in enumerate(lexical_hits)}
    dense_rank = {hit.chunk_id: i + 1 for i, hit in enumerate(dense_hits)}

    all_chunk_ids = set(lexical_rank) | set(dense_rank)
    if not all_chunk_ids:
        return []

    fused_scores: dict[uuid.UUID, float] = {}
    for chunk_id in all_chunk_ids:
        score = 0.0
        if chunk_id in lexical_rank:
            score += 1.0 / (RRF_K + lexical_rank[chunk_id])
        if chunk_id in dense_rank:
            score += 1.0 / (RRF_K + dense_rank[chunk_id])
        fused_scores[chunk_id] = score

    ranked_ids = sorted(fused_scores, key=lambda cid: fused_scores[cid], reverse=True)[:top_k]

    chunks_by_id = {
        c.id: c for c in (await db.execute(select(Chunk).where(Chunk.id.in_(ranked_ids)))).scalars()
    }

    return [
        RetrievedChunk(
            chunk=chunks_by_id[cid],
            fused_score=fused_scores[cid],
            lexical_rank=lexical_rank.get(cid),
            dense_rank=dense_rank.get(cid),
        )
        for cid in ranked_ids
        if cid in chunks_by_id
    ]
