from __future__ import annotations

import hashlib
import struct

from app.core.config import get_settings
from app.services.retrieval.ports import EmbeddingProvider


class FakeEmbeddingProvider:
    """Deterministic, dependency-free embedding provider for tests and for
    `LLM_PROVIDER=fake`. Encodes term overlap loosely via hashed n-grams so
    unit tests can assert that near-duplicate text embeds "close" without
    needing a real model.
    """

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            (bucket,) = struct.unpack("I", digest[:4])
            vector[bucket % self.dimensions] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)


class OllamaEmbeddingProvider:
    """Wraps `langchain_ollama.OllamaEmbeddings` behind the shared
    `EmbeddingProvider` port. Requires a local Ollama server with the
    configured embedding model pulled (`ollama pull nomic-embed-text`).
    """

    def __init__(self, dimensions: int | None = None) -> None:
        from langchain_ollama import OllamaEmbeddings

        settings = get_settings()
        self.dimensions = dimensions or settings.embedding_dimensions
        self._client = OllamaEmbeddings(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._client.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self._client.aembed_query(text)


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeEmbeddingProvider(dimensions=settings.embedding_dimensions)
    return OllamaEmbeddingProvider(dimensions=settings.embedding_dimensions)
