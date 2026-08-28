"""Extracts just the unified-diff portion out of a raw LLM patch-proposal
response.

Small local chat models very commonly wrap a diff in a markdown code fence
(```diff ... ```) despite being asked for a raw unified diff, and follow it
with the "Test command:"/"Citations:" lines the prompt also asks for. Feeding
the fence markers or trailing prose straight into `git apply` fails with
"corrupt patch" even when the diff itself is otherwise fine -- this was
observed directly against a real local Ollama model during manual
verification, not a hypothetical case.

A second, real failure mode observed against a live local model: it emitted a
blank *context* line inside a hunk with no leading space marker at all (a
bare "" line where unified-diff format requires " " for an unchanged blank
line). `_repair_hunk_line_markers` fixes exactly that one well-understood,
common LLM mistake by prepending a context marker to any in-hunk line that
doesn't already start with a valid one.

Neither of these is a general-purpose diff fixer: a genuinely malformed hunk
(wrong content, wrong line counts) still correctly fails `git apply` in the
sandbox (`services/patch/sandbox.py`) -- that rejection is the safety
mechanism working as intended, not a bug to paper over.
"""

from __future__ import annotations

import re

_FENCED_BLOCK_RE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)
_TRAILING_METADATA_RE = re.compile(r"^(Test command:|Citations:).*$", re.IGNORECASE | re.MULTILINE)
_HUNK_HEADER_RE = re.compile(r"^@@ .*@@")
_VALID_HUNK_LINE_PREFIXES = (" ", "+", "-", "\\")


def _repair_hunk_line_markers(lines: list[str]) -> list[str]:
    repaired: list[str] = []
    in_hunk = False
    for line in lines:
        if line.startswith(("--- ", "+++ ")):
            in_hunk = False
        elif _HUNK_HEADER_RE.match(line):
            in_hunk = True
        elif in_hunk and line and not line.startswith(_VALID_HUNK_LINE_PREFIXES):
            line = " " + line
        elif in_hunk and line == "":
            line = " "
        repaired.append(line)
    return repaired


def extract_diff_text(raw_response: str) -> str:
    fence_match = _FENCED_BLOCK_RE.search(raw_response)
    body = fence_match.group(1) if fence_match else raw_response
    body = _TRAILING_METADATA_RE.sub("", body)

    lines = body.split("\n")
    # Drop leading/trailing lines that are truly empty (blank prose padding,
    # or the empty line left behind where a "Test command:"/"Citations:"
    # line was removed above) -- but deliberately not via a plain `.strip()`,
    # which would also eat a unified diff's trailing *context* lines for a
    # blank source line. Those are represented as a single leading space
    # (" "), never a fully empty string, once `_repair_hunk_line_markers`
    # below has run -- so this boundary trim must happen first, while an
    # in-hunk blank line is still distinguishable as truly empty.
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()

    lines = _repair_hunk_line_markers(lines)
    return "\n".join(lines) + "\n"
