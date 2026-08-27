from __future__ import annotations

from app.services.agents.citations import ResolvedCitation, parse_cited_indices, resolve_citations


def test_parse_cited_indices_extracts_a_list():
    assert parse_cited_indices("The bug is here.\nCitations: [1, 3]") == [1, 3]


def test_parse_cited_indices_returns_empty_for_missing_line():
    assert parse_cited_indices("No citations line here.") == []


def test_parse_cited_indices_handles_single_index():
    assert parse_cited_indices("Citations: [2]") == [2]


def test_resolve_citations_drops_indices_the_model_hallucinated():
    excerpts = {1: ResolvedCitation("a.py", 1, 5, "chunk-1")}
    resolved = resolve_citations("Citations: [1, 99]", excerpts)
    assert resolved == [excerpts[1]]


def test_resolve_citations_falls_back_to_all_excerpts_when_none_cited():
    excerpts = {1: ResolvedCitation("a.py", 1, 5, "chunk-1"), 2: ResolvedCitation("b.py", 10, 20, "chunk-2")}
    resolved = resolve_citations("An answer with no citations line.", excerpts)
    assert set(resolved) == set(excerpts.values())


def test_resolve_citations_returns_empty_when_nothing_was_retrieved():
    assert resolve_citations("Citations: [1]", {}) == []
