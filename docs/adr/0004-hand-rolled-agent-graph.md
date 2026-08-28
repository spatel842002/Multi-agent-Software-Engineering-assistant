# ADR 0004: A hand-rolled deterministic graph executor instead of LangGraph

## Status

Accepted.

## Context

The three agent workflows need "graph-style" orchestration: an explicit
sequence of named steps, with the patch-proposal workflow requiring a real
branch point (a human-approval gate that the graph cannot cross on its
own). LangGraph is the natural off-the-shelf choice for this in the
LangChain ecosystem.

## Decision

`services/agents/graph.py` implements a ~60-line `WorkflowGraph`: a list of
named `GraphNode`s executed in order against a shared `GraphContext`, which
a node can halt by setting `context.halt = True`. The patch-proposal
workflow's `persist_proposal` step sets a `PENDING_APPROVAL` row and
returns; no node capable of applying a diff or running a subprocess is
reachable from that graph at all — the continuation lives in a separate
module (`services/patch/service.py`), invoked only by an explicit approval
API call.

LangGraph was deliberately not adopted for this project, given:

- The three workflows are short and mostly linear, with exactly one real
  branch point (the approval gate) that's better expressed as "the graph
  doesn't reach that code" than as a conditional edge in a larger state
  machine.
- A hand-rolled executor is trivially auditable in one file, with no
  additional dependency surface, checkpointing/persistence semantics, or
  LangGraph-specific concepts (channels, reducers) to learn to safely
  review a change to it.
- LangChain's other pieces (text splitters for chunking, the Ollama chat/
  embedding clients) are still used directly where they're a good fit —
  this is not a rejection of the LangChain ecosystem, just of adopting its
  heaviest orchestration layer for a workflow shape that doesn't need it.

## Consequences

- Adding a workflow with genuinely complex branching (parallel fan-out,
  cycles, retries-with-backoff as graph edges) would be more naturally
  expressed in LangGraph than by extending this executor — if that need
  arises, revisit this decision rather than growing `graph.py` into an ad
  hoc reimplementation of LangGraph.
- `WorkflowGraph` has no built-in persistence/checkpointing; a crashed
  workflow mid-run is simply lost (the caller sees an exception). Given
  every workflow here is a synchronous request/response call, not a
  long-running background process, this has been an acceptable trade-off.
