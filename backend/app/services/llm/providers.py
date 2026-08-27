from __future__ import annotations

import time
from collections.abc import Callable

from app.core.config import get_settings
from app.services.llm.ports import ChatCompletion, ChatMessage, ChatProvider


class FakeChatProvider:
    """Deterministic chat provider for tests and `LLM_PROVIDER=fake`.

    By default echoes a templated, clearly-fake response derived from the
    last user message. Tests that need to control the exact response inject
    a `responder` callable instead.
    """

    def __init__(self, responder: Callable[[list[ChatMessage]], str] | None = None) -> None:
        self._responder = responder or self._default_responder

    @staticmethod
    def _default_responder(messages: list[ChatMessage]) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[fake-llm-response] {last_user[:200]}"

    async def complete(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> ChatCompletion:
        start = time.perf_counter()
        content = self._responder(messages)
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ChatCompletion(content=content, latency_ms=latency_ms, model="fake")


class OllamaChatProvider:
    """Wraps `langchain_ollama.ChatOllama`. Requires a local Ollama server with
    the configured chat model pulled (e.g. `ollama pull qwen2.5-coder:1.5b`).
    """

    def __init__(self) -> None:
        from langchain_ollama import ChatOllama

        settings = get_settings()
        self._model_name = settings.ollama_chat_model
        self._client = ChatOllama(base_url=settings.ollama_base_url, model=settings.ollama_chat_model)

    async def complete(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> ChatCompletion:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        role_to_type = {"system": SystemMessage, "user": HumanMessage, "assistant": AIMessage}
        lc_messages = [role_to_type[m.role](content=m.content) for m in messages]

        start = time.perf_counter()
        response = await self._client.ainvoke(lc_messages, temperature=temperature)
        latency_ms = int((time.perf_counter() - start) * 1000)

        content = response.content if isinstance(response.content, str) else str(response.content)
        return ChatCompletion(content=content, latency_ms=latency_ms, model=self._model_name)


def get_chat_provider() -> ChatProvider:
    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeChatProvider()
    return OllamaChatProvider()
