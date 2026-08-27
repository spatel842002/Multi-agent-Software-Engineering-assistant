from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.services.retrieval.ports import VectorHit, VectorStore

_REPOSITORY_ID_FIELD = "repository_id"


class QdrantVectorStore:
    """Dense vector index backed by Qdrant. Points are keyed by chunk UUID and
    payload-filtered by `repository_id`, so a single collection serves every
    ingested repository without cross-repository leakage in search results.
    """

    def __init__(self, client: AsyncQdrantClient | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = client or AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        )

    async def ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}
        if self._settings.qdrant_collection not in existing:
            await self._client.create_collection(
                collection_name=self._settings.qdrant_collection,
                vectors_config=models.VectorParams(
                    size=self._settings.embedding_dimensions, distance=models.Distance.COSINE
                ),
            )
            await self._client.create_payload_index(
                collection_name=self._settings.qdrant_collection,
                field_name=_REPOSITORY_ID_FIELD,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def upsert_chunks(
        self, *, repository_id: uuid.UUID, chunk_ids: list[uuid.UUID], vectors: list[list[float]]
    ) -> None:
        if not chunk_ids:
            return
        await self.ensure_collection()
        points = [
            models.PointStruct(
                id=str(chunk_id),
                vector=vector,
                payload={_REPOSITORY_ID_FIELD: str(repository_id)},
            )
            for chunk_id, vector in zip(chunk_ids, vectors, strict=True)
        ]
        await self._client.upsert(collection_name=self._settings.qdrant_collection, points=points)

    async def search(
        self, *, repository_id: uuid.UUID, query_vector: list[float], top_k: int
    ) -> list[VectorHit]:
        await self.ensure_collection()
        results = await self._client.query_points(
            collection_name=self._settings.qdrant_collection,
            query=query_vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key=_REPOSITORY_ID_FIELD, match=models.MatchValue(value=str(repository_id))
                    )
                ]
            ),
            limit=top_k,
        )
        return [VectorHit(chunk_id=uuid.UUID(str(p.id)), score=p.score) for p in results.points]

    async def delete_repository(self, *, repository_id: uuid.UUID) -> None:
        await self.ensure_collection()
        await self._client.delete(
            collection_name=self._settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key=_REPOSITORY_ID_FIELD, match=models.MatchValue(value=str(repository_id))
                        )
                    ]
                )
            ),
        )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


class InMemoryVectorStore:
    """A `VectorStore` implementation backing `LLM_PROVIDER=fake`: exact
    brute-force cosine search over an in-process dict, used wherever a real
    Qdrant instance isn't available (tests, and any environment that opts
    into the fully-local fake provider mode). Not distributed, not
    persistent -- `get_vector_store()` below is the only supported way to
    obtain one, as a process-wide singleton, so state upserted by ingestion
    is visible to a later search within the same process.
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


_fake_singleton: InMemoryVectorStore | None = None


def get_vector_store() -> VectorStore:
    settings = get_settings()
    if settings.llm_provider == "fake":
        global _fake_singleton
        if _fake_singleton is None:
            _fake_singleton = InMemoryVectorStore()
        return _fake_singleton
    return QdrantVectorStore()
