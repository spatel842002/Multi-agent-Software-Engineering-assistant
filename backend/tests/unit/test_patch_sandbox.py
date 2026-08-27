from __future__ import annotations

from app.services.patch.sandbox import run_patch_in_sandbox

VALID_DIFF = """--- a/greet.py
+++ b/greet.py
@@ -1 +1 @@
-print("hello")
+print("hello world")
"""

INVALID_DIFF = """--- a/does_not_exist.py
+++ b/does_not_exist.py
@@ -1 +1 @@
-nope
+nope nope
"""


def test_applies_a_valid_diff_and_runs_a_passing_test(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "greet.py").write_text('print("hello")\n')

    result = run_patch_in_sandbox(
        source_repo_path=repo,
        diff_text=VALID_DIFF,
        test_command='python -c "print(1)"',
    )

    assert result.apply_succeeded is True
    assert result.test_ran is True
    assert result.test_succeeded is True
    # The original file must be untouched -- the patch only ever lands in the sandbox copy.
    assert (repo / "greet.py").read_text() == 'print("hello")\n'

    get_settings.cache_clear()


def test_apply_failure_is_reported_without_running_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "greet.py").write_text('print("hello")\n')

    result = run_patch_in_sandbox(
        source_repo_path=repo, diff_text=INVALID_DIFF, test_command="echo should-not-run"
    )

    assert result.apply_succeeded is False
    assert result.test_ran is False

    get_settings.cache_clear()


def test_no_test_command_still_applies_and_reports_no_test_run(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))
    from app.core.config import get_settings

    get_settings.cache_clear()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "greet.py").write_text('print("hello")\n')

    result = run_patch_in_sandbox(source_repo_path=repo, diff_text=VALID_DIFF, test_command=None)

    assert result.apply_succeeded is True
    assert result.test_ran is False

    get_settings.cache_clear()
