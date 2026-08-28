from __future__ import annotations

from app.services.agents.diff_extraction import extract_diff_text

RAW_DIFF = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"


def test_extracts_a_fenced_diff_block_and_strips_the_fence():
    raw_response = f"```diff\n{RAW_DIFF}```\n\nTest command: pytest -q\n\nCitations: [1]"
    assert extract_diff_text(raw_response) == RAW_DIFF


def test_extracts_a_plain_unlabeled_fence():
    raw_response = f"```\n{RAW_DIFF}```"
    assert extract_diff_text(raw_response) == RAW_DIFF


def test_passes_through_an_unfenced_diff_stripping_trailing_metadata():
    raw_response = f"{RAW_DIFF}\nTest command: pytest -q\nCitations: [1, 2]"
    assert extract_diff_text(raw_response) == RAW_DIFF


def test_handles_a_diff_with_no_trailing_metadata_at_all():
    assert extract_diff_text(RAW_DIFF) == RAW_DIFF


def test_preserves_trailing_blank_context_lines_the_hunk_header_counts_on():
    """Regression test: a naive `.strip()` would delete a diff's trailing
    blank *context* lines (represented as a lone space, not an empty
    string) along with real trailing whitespace, desyncing the hunk header's
    declared line count from its actual content and making `git apply`
    reject an otherwise-valid diff with "corrupt patch". This is exactly
    what `difflib.unified_diff` produces for a source file with trailing
    blank lines, which is common.
    """
    diff_with_trailing_blank_context = (
        "--- a/foo.py\n+++ b/foo.py\n@@ -1,3 +1,3 @@\n-old\n+new\n context\n \n \n"
    )
    raw_response = (
        f"```diff\n{diff_with_trailing_blank_context}```\n\nTest command: pytest -q\n\nCitations: [1]"
    )
    assert extract_diff_text(raw_response) == diff_with_trailing_blank_context


def test_repairs_a_mid_hunk_blank_line_missing_its_context_marker():
    """Regression test for a real failure observed against a live local
    Ollama model: it emitted a hunk with a bare blank line (no leading space)
    where an unchanged blank source line should have been marked as context,
    which `git apply` correctly rejected as "corrupt patch". The fix
    normalizes that one well-understood mistake rather than requiring exact
    formatting discipline from a small local model.
    """
    malformed = "--- a/foo.py\n+++ b/foo.py\n@@ -1,4 +1,4 @@\n context1\n-old\n+new\n\n import unittest\n"
    repaired = "--- a/foo.py\n+++ b/foo.py\n@@ -1,4 +1,4 @@\n context1\n-old\n+new\n \n import unittest\n"
    assert extract_diff_text(malformed) == repaired


def test_does_not_touch_lines_outside_a_hunk():
    # A blank line between the file headers and the first hunk (or after the
    # last hunk closes) is not diff content and must be left as a real blank
    # line, not turned into a stray " " context marker with nothing to apply.
    raw = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"
    assert extract_diff_text(raw) == raw
