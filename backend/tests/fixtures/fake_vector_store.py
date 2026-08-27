"""Re-exports `InMemoryVectorStore` for tests. The implementation lives in
`app.services.retrieval.vector_store` because it's also a real, supported
runtime mode (`LLM_PROVIDER=fake`), not just a test double.
"""

from __future__ import annotations

from app.services.retrieval.vector_store import InMemoryVectorStore

__all__ = ["InMemoryVectorStore"]
