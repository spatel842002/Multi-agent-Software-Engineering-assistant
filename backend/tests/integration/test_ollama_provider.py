"""Exercises the real `OllamaChatProvider` / `OllamaEmbeddingProvider` against
a real Ollama server. Skipped automatically when no Ollama server is
reachable, since the fast/default test suite must not depend on it -- but
running it catches exactly the class of bug that a fully-mocked or
`LLM_PROVIDER=fake` test suite cannot: the LangChain/Ollama client call
signature actually being correct (this test caught a real
`AsyncClient.chat() got an unexpected keyword argument 'temperature'` bug in
`providers.py` during manual `docker compose` verification).

Requires `ollama pull qwen2.5-coder:1.5b` and `ollama pull nomic-embed-text`
to have been run against the target server first.
"""

from __future__ import annotations

import os

import httpx
import pytest

from app.services.llm.ports import ChatMessage
from app.services.llm.providers import OllamaChatProvider
from app.services.retrieval.embeddings import OllamaEmbeddingProvider

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


def _ollama_reachable() -> bool:
    try:
        return httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(not _ollama_reachable(), reason=f"No Ollama server reachable at {OLLAMA_BASE_URL}"),
]


async def test_ollama_chat_provider_completes_a_real_prompt():
    provider = OllamaChatProvider()
    completion = await provider.complete(
        [
            ChatMessage(role="system", content="Answer in exactly one word."),
            ChatMessage(role="user", content="Say 'hello'."),
        ]
    )
    assert completion.content.strip()
    assert completion.latency_ms >= 0


async def test_ollama_embedding_provider_returns_a_real_vector():
    provider = OllamaEmbeddingProvider()
    vectors = await provider.embed_documents(["def add(a, b): return a + b"])
    assert len(vectors) == 1
    assert len(vectors[0]) == provider.dimensions
    assert any(v != 0 for v in vectors[0])
