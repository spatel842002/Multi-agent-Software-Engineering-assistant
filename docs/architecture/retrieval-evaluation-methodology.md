# Retrieval and evaluation methodology

## What `evals/run_evals.py` measures, honestly

This is a small, reproducible evaluation harness, not a statistically
powerful benchmark. The golden set (`evals/golden_dataset.py`) has 5 QA/bug
items and 1 patch item, all against the fixture repository checked into
`backend/tests/fixtures/sample_repo/` — a tiny, hand-written Python module.
It exists to make the *evaluation methodology itself* real, reproducible,
and regression-tested, not to produce a number that means "the system is
X% accurate" in any general sense. Treat the numbers as a smoke test with
metrics attached, not a leaderboard score.

## The two run modes

- **`--provider fake`** (default): a deterministic fake LLM/embedding
  provider, no network access, same numbers on every machine. This
  evaluates the *retrieval and citation-grounding plumbing* — did the
  right file get retrieved, did the citation-resolution logic correctly
  keep only real citations, did the sandbox correctly apply a
  known-good diff. It says nothing about real answer quality, because the
  fake provider doesn't generate real answers.
- **`--provider ollama`**: the same golden set against a real local model.
  This is the only mode that measures real answer/patch quality, and its
  numbers depend on the model, the prompt, and the hardware it ran on —
  every committed `docs/benchmarks/eval_report_*.json` records which
  provider produced it.

## Metrics (`evals/metrics.py`)

| Metric | What it actually measures | What it does NOT measure |
|---|---|---|
| `retrieval_quality` (hit@k) | Fraction of golden questions where the expected file appears anywhere in hybrid retrieval's results | Whether the *right chunk within* that file was retrieved, or whether the answer used it correctly |
| `groundedness` | Fraction of answers where every citation resolved to a chunk that was actually retrieved | This is enforced by construction in `services/agents/citations.py` and should always be 1.0 — the eval re-checks it as a regression guard, not as a real discriminating signal |
| `citation_accuracy` | Fraction of answers that cited the expected file specifically | A model can cite the *wrong* excerpt from the *right* file and still count here |
| `qa_latency` / `patch_latency` | Real wall-clock mean/p95 per call | Nothing about correctness |
| `qa_task_success` | A **proxy**: non-empty answer + at least one citation | **Not factual correctness.** No human-graded "is this answer actually right" label exists in this dataset. Do not read this as an accuracy score. |
| `patch_task_success` (`apply_success_rate`) | Fraction of proposed diffs that applied cleanly with `git apply` in the sandbox | Whether the change was semantically correct, or whether its test command could even run (see the sandbox limitation below) |

## A real, honest finding from running this against a real model

Running `--provider ollama` during development surfaced three genuine bugs
(documented in `CHANGELOG.md`'s "Fixed" section) that the `--provider fake`
mode's mocked responses could never have caught: an invalid LLM client call
signature, markdown-fenced/backtick-wrapped diff output requiring a real
extraction step, and a Windows-specific subprocess text-encoding bug that
silently corrupted diffs before `git apply` ever saw them. This is the
concrete argument for why this project treats "runs against mocks" and
"runs against the real stack" as two different, both-necessary levels of
verification — see `docs/testing.md`.

## Known limitation: the patch sandbox and `patch_task_success`

`services/patch/sandbox.py` applies a diff and, if it applies, runs the
proposed test command in a disposable copy of the repository — but it does
not install that repository's own test dependencies (an arbitrary target
repo's `requirements.txt`/`package.json` are not installed into the sandbox
container). This means `test_command` execution commonly fails with
"command not found" even when `git apply` itself succeeded. Real evidence:
see `docs/assets/screenshots/patch_decision_response_final.json` — a diff
that applied cleanly, followed by `pytest: not found`. This is a documented
scope boundary (see `docs/adr/0003-process-level-sandbox-isolation.md`),
not something `patch_task_success` currently distinguishes from a genuine
apply failure — a real place this metric could be split further.

## Reproducing a report

```bash
python evals/run_evals.py --provider fake                       # docs/benchmarks/eval_report_fake.json
python evals/run_evals.py --provider ollama                     # docs/benchmarks/eval_report_ollama.json
python evals/run_evals.py --provider fake --skip-mlflow          # report file only, no MLflow dependency
```

Every run also logs to MLflow (`MLFLOW_TRACKING_URI`, defaulting to a
temporary local sqlite store; point it at the Compose `mlflow` service's
`http://localhost:5000` to browse runs in its UI).
