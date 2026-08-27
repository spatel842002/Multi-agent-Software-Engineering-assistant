from __future__ import annotations

from app.services.ingestion.chunking import chunk_file_content


def test_empty_content_produces_no_chunks():
    assert chunk_file_content("", language="python") == []


def test_short_content_produces_a_single_chunk_covering_full_span():
    content = "def f():\n    return 1\n"
    chunks = chunk_file_content(content, language="python")
    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == content.count("\n")


def test_chunk_line_span_can_be_sliced_back_out_of_the_original_content():
    content = "\n".join(f"line {i}" for i in range(1, 30))
    chunks = chunk_file_content(content, language="text")
    lines = content.split("\n")
    for chunk in chunks:
        # start_line/end_line are 1-indexed and inclusive.
        reconstructed = "\n".join(lines[chunk.start_line - 1 : chunk.end_line])
        assert chunk.content in reconstructed or reconstructed in chunk.content


def test_large_content_is_split_into_multiple_chunks():
    content = "\n".join(f"def function_{i}():\n    return {i}\n" for i in range(200))
    chunks = chunk_file_content(content, language="python")
    assert len(chunks) > 1
    # Every chunk must fall inside the document's real line range.
    total_lines = content.count("\n") + 1
    assert all(1 <= c.start_line <= c.end_line <= total_lines for c in chunks)
