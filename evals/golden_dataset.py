"""A small, hand-curated "golden" evaluation set against the checked-in
fixture repository (`backend/tests/fixtures/sample_repo`), so evaluation is
fully reproducible from a clean clone with no network access or external
data dependency.

Each item's `expected_file` is the file a correct, grounded answer must cite
-- this is the ground truth `retrieval_quality.py` and `groundedness.py`
check against. This is intentionally small (a handful of items): it exists
to make the *evaluation methodology* itself real, reproducible, and testable,
not to be a statistically powerful benchmark -- see
`docs/architecture/retrieval-evaluation-methodology.md` for the honest scope
of what this does and does not measure.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenQAItem:
    question: str
    expected_file: str


@dataclass(frozen=True)
class GoldenPatchItem:
    task_description: str
    expected_file: str


QA_GOLDEN_SET: list[GoldenQAItem] = [
    GoldenQAItem("What does the divide function do?", "calculator.py"),
    GoldenQAItem("What happens if you divide by zero in this codebase?", "calculator.py"),
    GoldenQAItem("What method resets the Calculator's running total?", "calculator.py"),
    GoldenQAItem("What is this repository for?", "README.md"),
]

BUG_INVESTIGATION_GOLDEN_SET: list[GoldenQAItem] = [
    GoldenQAItem(
        "Users report a ZeroDivisionError crash. Where does that come from?", "calculator.py"
    ),
]

PATCH_GOLDEN_SET: list[GoldenPatchItem] = [
    GoldenPatchItem("Guard divide() against division by zero.", "calculator.py"),
]
