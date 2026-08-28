"""Individual eval metric computations. Each function takes the raw
per-item results collected by `run_evals.py` and returns a small dict of
aggregate numbers, so each metric's definition is auditable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QAEvalItemResult:
    question: str
    expected_file: str
    retrieved_files: list[str]
    answer: str
    cited_files: list[str]
    latency_ms: int
    all_citations_resolved: bool


@dataclass
class PatchEvalItemResult:
    task_description: str
    expected_file: str
    target_files: list[str]
    diff_applies_cleanly: bool
    latency_ms: int


def retrieval_quality(items: list[QAEvalItemResult]) -> dict[str, float]:
    """Hit@k: fraction of golden questions where the expected file appears
    anywhere in the set of files hybrid retrieval actually returned.
    """
    if not items:
        return {"hit_rate": 0.0, "n": 0}
    hits = sum(1 for i in items if i.expected_file in i.retrieved_files)
    return {"hit_rate": hits / len(items), "n": len(items)}


def groundedness(items: list[QAEvalItemResult]) -> dict[str, float]:
    """Fraction of answers where every citation resolved to a real, retrieved
    chunk -- i.e. nothing was fabricated. This should always be 1.0 by
    construction (`services/agents/citations.py` never emits an
    unresolvable citation); the eval re-checks it as a regression guard.
    """
    if not items:
        return {"groundedness_rate": 0.0, "n": 0}
    grounded = sum(1 for i in items if i.all_citations_resolved)
    return {"groundedness_rate": grounded / len(items), "n": len(items)}


def citation_accuracy(items: list[QAEvalItemResult]) -> dict[str, float]:
    """Fraction of answers that cited the expected file specifically (a
    stricter, precision-oriented sibling of `retrieval_quality`: retrieval
    can surface the right file without the model actually citing it).
    """
    if not items:
        return {"citation_accuracy": 0.0, "n": 0}
    correct = sum(1 for i in items if i.expected_file in i.cited_files)
    return {"citation_accuracy": correct / len(items), "n": len(items)}


def latency(items: list[QAEvalItemResult] | list[PatchEvalItemResult]) -> dict[str, float]:
    if not items:
        return {"mean_ms": 0.0, "p95_ms": 0.0, "n": 0}
    values = sorted(i.latency_ms for i in items)
    p95_index = min(len(values) - 1, int(round(0.95 * (len(values) - 1))))
    return {"mean_ms": sum(values) / len(values), "p95_ms": float(values[p95_index]), "n": len(values)}


def qa_task_success(items: list[QAEvalItemResult]) -> dict[str, float]:
    """A proxy for "the workflow did something useful", not a human-graded
    correctness score: an answer counts as successful if it is non-empty AND
    grounded in at least one citation. This deliberately does NOT claim to
    measure factual correctness -- see the evaluation methodology doc for why.
    """
    if not items:
        return {"success_rate": 0.0, "n": 0}
    successes = sum(1 for i in items if i.answer.strip() and i.cited_files)
    return {"success_rate": successes / len(items), "n": len(items)}


def patch_task_success(items: list[PatchEvalItemResult]) -> dict[str, float]:
    """Fraction of proposed patches whose diff applied cleanly with `git
    apply` in the sandbox -- i.e. the proposal was at least syntactically
    usable, independent of whether the change was semantically correct.
    """
    if not items:
        return {"apply_success_rate": 0.0, "n": 0}
    applied = sum(1 for i in items if i.diff_applies_cleanly)
    return {"apply_success_rate": applied / len(items), "n": len(items)}
