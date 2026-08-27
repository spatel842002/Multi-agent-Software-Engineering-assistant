"""Splits file content into retrieval-sized chunks using LangChain's
recursive character text splitter, language-aware where LangChain ships a
grammar (Python, Markdown, ...), falling back to a generic splitter
otherwise.

`RecursiveCharacterTextSplitter` returns raw text chunks with no positional
metadata, but citations require real line numbers, so this module locates
each chunk back in the original text (via a forward-scanning search, since
chunk_overlap means content can legitimately repeat) and converts its offset
to a 1-indexed [start_line, end_line] span.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

_LANGCHAIN_LANGUAGE_BY_NAME = {
    "python": Language.PYTHON,
    "markdown": Language.MARKDOWN,
    "typescript": Language.TS,
    "javascript": Language.JS,
    "go": Language.GO,
    "rust": Language.RUST,
    "java": Language.JAVA,
}


@dataclass(frozen=True)
class ContentChunk:
    content: str
    start_line: int
    end_line: int


def _splitter_for(language: str) -> RecursiveCharacterTextSplitter:
    lc_language = _LANGCHAIN_LANGUAGE_BY_NAME.get(language)
    if lc_language is not None:
        return RecursiveCharacterTextSplitter.from_language(
            lc_language, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
    return RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)


def chunk_file_content(content: str, *, language: str) -> list[ContentChunk]:
    if not content.strip():
        return []

    splitter = _splitter_for(language)
    raw_chunks = splitter.split_text(content)

    results: list[ContentChunk] = []
    search_from = 0
    for raw in raw_chunks:
        offset = content.find(raw, search_from)
        if offset == -1:
            # Overlap search regressed past this chunk's true position (rare,
            # happens with repeated boilerplate); fall back to a from-start search.
            offset = content.find(raw)
        if offset == -1:
            continue
        start_line = content.count("\n", 0, offset) + 1
        end_line = start_line + raw.count("\n")
        results.append(ContentChunk(content=raw, start_line=start_line, end_line=end_line))
        search_from = max(search_from, offset + max(len(raw) - CHUNK_OVERLAP, 1))

    return results
