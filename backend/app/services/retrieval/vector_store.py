from __future__ import annotations

import uuid

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.services.retrieval.ports import VectorHit

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
