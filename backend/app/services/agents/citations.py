"""Parses the "Citations: [1, 3]" line an LLM response is instructed to end
with, and resolves each index back to the retrieved chunk it refers to.

Groundedness enforcement lives here: if the model cites an index that wasn't
actually retrieved, that index is silently dropped rather than fabricated
into a citation -- a citation in this system is only ever produced from a
real, resolvable (file_path, start_line, end_line), never from LLM text
alone. If the model cites nothing (or nothing resolvable), the caller falls
back to citing every retrieved excerpt, so an answer is never delivered with
zero evidence trail when evidence was in fact retrieved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CITATIONS_LINE_RE = re.compile(r"Citations:\s*\[([0-9,\s]*)\]", re.IGNORECASE)


@dataclass(frozen=True)
class ResolvedCitation:
    file_path: str
    start_line: int
    end_line: int
    chunk_id: object  # uuid.UUID, kept loosely typed to avoid a model import cycle


def parse_cited_indices(llm_output: str) -> list[int]:
    match = _CITATIONS_LINE_RE.search(llm_output)
    if not match:
        return []
    raw = match.group(1)
    indices: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit():
            indices.append(int(token))
    return indices


def resolve_citations(
    llm_output: str, excerpts_by_index: dict[int, ResolvedCitation]
) -> list[ResolvedCitation]:
    cited_indices = parse_cited_indices(llm_output)
    resolved = [excerpts_by_index[i] for i in cited_indices if i in excerpts_by_index]
    if resolved:
        return resolved
    # No (resolvable) citation line: fall back to citing everything that was
    # actually retrieved, so groundedness never silently drops to zero.
    return list(excerpts_by_index.values())
