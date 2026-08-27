from __future__ import annotations

import uuid

from app.services.retrieval.ports import VectorHit


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class InMemoryVectorStore:
    """A `VectorStore` test double: exact brute-force cosine search over an
    in-process dict. Used by unit/integration tests that need real hybrid
    retrieval behavior without requiring a running Qdrant instance.
    """

    def __init__(self) -> None:
        self._vectors: dict[uuid.UUID, tuple[uuid.UUID, list[float]]] = {}

    async def upsert_chunks(
        self, *, repository_id: uuid.UUID, chunk_ids: list[uuid.UUID], vectors: list[list[float]]
    ) -> None:
        for chunk_id, vector in zip(chunk_ids, vectors, strict=True):
            self._vectors[chunk_id] = (repository_id, vector)

    async def search(
        self, *, repository_id: uuid.UUID, query_vector: list[float], top_k: int
    ) -> list[VectorHit]:
        candidates = [
            (chunk_id, vector)
            for chunk_id, (repo_id, vector) in self._vectors.items()
            if repo_id == repository_id
        ]
        scored = [
            VectorHit(chunk_id=chunk_id, score=_cosine_similarity(query_vector, vector))
            for chunk_id, vector in candidates
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    async def delete_repository(self, *, repository_id: uuid.UUID) -> None:
        self._vectors = {cid: v for cid, v in self._vectors.items() if v[0] != repository_id}
