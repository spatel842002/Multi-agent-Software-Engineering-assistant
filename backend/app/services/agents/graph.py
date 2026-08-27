"""A small deterministic node-graph executor.

Each workflow (`workflows.py`) is expressed as named `GraphNode`s connected by
explicit edges, executed in order starting from `entrypoint`. A node can
short-circuit the graph by setting `context.halt = True` -- this is how the
patch-proposal workflow enforces the human-approval gate: the
`persist_proposal` node halts the graph immediately after creating a
`PENDING_APPROVAL` row, and no node capable of touching the filesystem or
running a subprocess (`apply_and_test`, in `services/patch`) is reachable
from this graph at all. It lives in a separate module, invoked only by an
explicit approval API call.

This intentionally does not use LangGraph: the three workflows in this
system are short, mostly-linear pipelines with one gating point, so a
~60-line typed executor gives the same auditability with fewer moving parts
and no additional dependency surface. See `docs/adr/0004-hand-rolled-agent-graph.md`.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphContext:
    data: dict[str, object] = field(default_factory=dict)
    halt: bool = False
    trace: list[str] = field(default_factory=list)


NodeFn = Callable[[GraphContext], Awaitable[None]]


@dataclass(frozen=True)
class GraphNode:
    name: str
    fn: NodeFn


class WorkflowGraph:
    def __init__(self, name: str, nodes: list[GraphNode]) -> None:
        self.name = name
        self._nodes = nodes

    async def run(self, context: GraphContext) -> GraphContext:
        for node in self._nodes:
            if context.halt:
                break
            start = time.perf_counter()
            await node.fn(context)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            context.trace.append(node.name)
            logger.info("workflow_node_complete", workflow=self.name, node=node.name, elapsed_ms=elapsed_ms)
        return context
