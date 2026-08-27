from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    latency_ms: int
    model: str


class ChatProvider(Protocol):
    async def complete(self, messages: list[ChatMessage], *, temperature: float = 0.0) -> ChatCompletion: ...
