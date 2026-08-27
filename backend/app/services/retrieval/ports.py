"""Interfaces (Protocols) that decouple retrieval logic from the concrete LLM
provider and vector database, so the free local defaults (Ollama, Qdrant) and
any future hosted provider share one contract, and so unit tests can run
against fast in-memory fakes instead of real network services.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True)
class VectorHit:
    chunk_id: uuid.UUID
    score: float


class VectorStore(Protocol):
    async def upsert_chunks(
        self,
        *,
        repository_id: uuid.UUID,
        chunk_ids: list[uuid.UUID],
        vectors: list[list[float]],
    ) -> None: ...

    async def search(
        self, *, repository_id: uuid.UUID, query_vector: list[float], top_k: int
    ) -> list[VectorHit]: ...

    async def delete_repository(self, *, repository_id: uuid.UUID) -> None: ...
