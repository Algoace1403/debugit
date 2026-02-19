"""
Phase 5 tests: fix_validator node with mocked sandbox commands.
"""
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock, call

import pytest

from app.agents.nodes.fix_validator import fix_validator_node


VALID_DIFF = (
    "--- a/src/calc.py\n"
    "+++ b/src/calc.py\n"
    "@@ -19,1 +19,1 @@\n"
    "-    if x > 10:\n"
    "+    if x >= 10:\n"
)

PROPOSED_FIX = {
    "file": "src/calc.py",
    "bug_type": "LOGIC",
    "line_number": 19,
    "issue_line": "LOGIC error in src/calc.py line 19 → Fix: change > to >=",
    "diff": VALID_DIFF,
    "iteration": 1,
}


class TestFixValidator:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_empty_proposed_fixes(self):
        """No proposed fixes → empty fixes_applied."""
        state = {
            "proposed_fixes": [],
            "repo_path": "/tmp",
            "iteration": 1,
            "test_framework": "pytest",
            "package_manager": "pip",
        }
        result = self._run(fix_validator_node(state))
        assert result["fixes_applied"] == []

    def test_generation_error_skipped(self):
        """Fix with generation_error → status failed, no patch commands."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "proposed_fixes": [
                    {
                        "file": "main.py",
                        "bug_type": "SYNTAX",
                        "line_number": 5,
                        "issue_line": "SYNTAX error in main.py line 5 → Fix: fix",
                        "diff": "",
                        "iteration": 1,
                        "generation_error": "LLM error: rate limited",
                    }
                ],
                "repo_path": tmpdir,
                "iteration": 1,
                "test_framework": "pytest",
                "package_manager": "pip",
            }
            result = self._run(fix_validator_node(state))

        assert len(result["fixes_applied"]) == 1
        assert result["fixes_applied"][0]["status"] == "failed"
        assert result["fixes_applied"][0]["bug_type"] == "SYNTAX"

    @patch("app.agents.nodes.fix_validator.run_tests")
    @patch("app.agents.nodes.fix_validator.run_command")
    def test_dry_run_fail_marks_failed(self, mock_run_cmd, mock_run_tests):
        """Patch dry-run fails → status failed, no apply, no test run."""
        mock_run_cmd.return_value = MagicMock(returncode=1, stdout="", stderr="patch failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the target file
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "calc.py"), "w") as f:
                f.write("def check(x):\n    if x > 10:\n        return True\n")

            state = {
                "proposed_fixes": [PROPOSED_FIX],
                "repo_path": tmpdir,
                "iteration": 1,
                "test_framework": "pytest",
                "package_manager": "pip",
            }
            result = self._run(fix_validator_node(state))

        assert len(result["fixes_applied"]) == 1
        assert result["fixes_applied"][0]["status"] == "failed"
        # run_command called once for dry-run only
        assert mock_run_cmd.call_count == 1
        assert "--dry-run" in mock_run_cmd.call_args[0][1]
        # Tests never ran
        mock_run_tests.assert_not_called()

    @patch("app.agents.nodes.fix_validator.run_tests")
    @patch("app.agents.nodes.fix_validator.run_command")
    def test_apply_ok_tests_pass(self, mock_run_cmd, mock_run_tests):
        """Patch applies cleanly + tests pass → status fixed."""
        # dry-run ok, apply ok
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # tests pass
        mock_run_tests.return_value = MagicMock(returncode=0, stdout="5 passed", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "calc.py"), "w") as f:
                f.write("def check(x):\n    if x > 10:\n        return True\n")

            state = {
                "proposed_fixes": [PROPOSED_FIX],
                "repo_path": tmpdir,
                "iteration": 1,
                "test_framework": "pytest",
                "package_manager": "pip",
            }
            result = self._run(fix_validator_node(state))

        fix = result["fixes_applied"][0]
        assert fix["status"] == "fixed"
        assert fix["file"] == "src/calc.py"
        assert fix["commit_message"].startswith("[AI-AGENT] Iteration 1:")
        assert fix["diff"] == VALID_DIFF
        # 2 run_command calls: dry-run + apply
        assert mock_run_cmd.call_count == 2
        mock_run_tests.assert_called_once()

    @patch("app.agents.nodes.fix_validator.subprocess")
    @patch("app.agents.nodes.fix_validator.run_tests")
    @patch("app.agents.nodes.fix_validator.run_command")
    def test_apply_ok_tests_fail_reverts(self, mock_run_cmd, mock_run_tests, mock_subprocess):
        """Patch applies but tests fail → status failed + revert attempted."""
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="", stderr="")
        # tests fail
        mock_run_tests.return_value = MagicMock(returncode=1, stdout="1 failed", stderr="")
        # git checkout succeeds
        mock_subprocess.run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            original = "def check(x):\n    if x > 10:\n        return True\n"
            with open(os.path.join(src_dir, "calc.py"), "w") as f:
                f.write(original)

            state = {
                "proposed_fixes": [PROPOSED_FIX],
                "repo_path": tmpdir,
                "iteration": 1,
                "test_framework": "pytest",
                "package_manager": "pip",
            }
            result = self._run(fix_validator_node(state))

        fix = result["fixes_applied"][0]
        assert fix["status"] == "failed"
        # git checkout was called for revert
        mock_subprocess.run.assert_called()
        git_call_args = mock_subprocess.run.call_args[0][0]
        assert "checkout" in git_call_args
        assert "src/calc.py" in git_call_args

    def test_invalid_repo_path_all_failed(self):
        """Invalid repo_path → all proposed fixes marked failed."""
        state = {
            "proposed_fixes": [PROPOSED_FIX, {**PROPOSED_FIX, "file": "other.py"}],
            "repo_path": "/nonexistent/path",
            "iteration": 2,
            "test_framework": "pytest",
            "package_manager": "pip",
        }
        result = self._run(fix_validator_node(state))
        assert len(result["fixes_applied"]) == 2
        assert all(f["status"] == "failed" for f in result["fixes_applied"])

    @patch("app.agents.nodes.fix_validator.run_tests")
    @patch("app.agents.nodes.fix_validator.run_command")
    def test_commit_message_format(self, mock_run_cmd, mock_run_tests):
        """Commit message matches spec format."""
        mock_run_cmd.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_tests.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "a.py"), "w") as f:
                f.write("x = 1\n")

            fix_syntax = {
                **PROPOSED_FIX,
                "file": "a.py",
                "bug_type": "SYNTAX",
                "diff": "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
            }
            state = {
                "proposed_fixes": [fix_syntax],
                "repo_path": tmpdir,
                "iteration": 3,
                "test_framework": "pytest",
                "package_manager": "pip",
            }
            result = self._run(fix_validator_node(state))

        assert result["fixes_applied"][0]["commit_message"] == "[AI-AGENT] Iteration 3: Fix SYNTAX issues"
