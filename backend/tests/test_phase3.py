"""
Phase 3 tests: repo_analyzer and test_runner with mocked I/O.
"""
import asyncio
import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest


# ─── repo_analyzer ───────────────────────────────────────────────
from app.agents.nodes.repo_analyzer import repo_analyzer_node


class TestRepoAnalyzer:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("app.agents.nodes.repo_analyzer.install_deps")
    @patch("app.agents.nodes.repo_analyzer.create_branch")
    @patch("app.agents.nodes.repo_analyzer.clone_repo")
    def test_sets_all_fields(self, mock_clone, mock_branch, mock_install):
        """repo_analyzer sets branch_name, language, package_manager, etc."""
        # Create a fake repo directory with a Python file
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = os.path.join(tmpdir, "test-run", "repo")

            def fake_clone(url, dest):
                os.makedirs(dest, exist_ok=True)
                # Create a minimal Python project
                with open(os.path.join(dest, "requirements.txt"), "w") as f:
                    f.write("pytest\n")
                with open(os.path.join(dest, "test_main.py"), "w") as f:
                    f.write("def test_ok(): pass\n")
                with open(os.path.join(dest, "main.py"), "w") as f:
                    f.write("print('hello')\n")

            mock_clone.side_effect = fake_clone
            mock_install.return_value = MagicMock(returncode=0, stdout="", stderr="")

            state = {
                "run_id": "test-run",
                "repo_url": "https://github.com/test/repo",
                "team_name": "Alpha Team",
                "leader_name": "Jane Doe",
            }

            with patch("app.agents.nodes.repo_analyzer.settings") as mock_settings:
                mock_settings.data_dir = tmpdir

                result = self._run(repo_analyzer_node(state))

            assert result["branch_name"] == "ALPHA_TEAM_JANE_DOE_AI_Fix"
            assert result["language"] == "python"
            assert result["package_manager"] == "pip"
            assert result["test_framework"] == "pytest"
            assert "test_main.py" in result["test_files"]
            assert "error" not in result or result["error"] is None
            assert result["current_node"] == "repo_analyzer"
            mock_clone.assert_called_once()
            mock_branch.assert_called_once()
            mock_install.assert_called_once()

    @patch("app.agents.nodes.repo_analyzer.clone_repo")
    def test_clone_failure_sets_error(self, mock_clone):
        """If clone fails, error is set and no crash."""
        mock_clone.side_effect = subprocess.CalledProcessError(128, "git clone")

        state = {
            "run_id": "fail-run",
            "repo_url": "https://github.com/test/bad",
            "team_name": "Team",
            "leader_name": "Lead",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.agents.nodes.repo_analyzer.settings") as mock_settings:
                mock_settings.data_dir = tmpdir
                result = self._run(repo_analyzer_node(state))

        assert result["error"] is not None
        assert result["branch_name"] == "TEAM_LEAD_AI_Fix"
        assert result["language"] == ""


# ─── test_runner ─────────────────────────────────────────────────
from app.agents.nodes.test_runner import (
    test_runner_node as _test_runner_node,
    _parse_pytest_stdout,
    _parse_jest_stdout,
)


class TestTestRunner:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    @patch("app.agents.nodes.test_runner.run_tests")
    def test_all_passing(self, mock_run):
        """When all tests pass, all_tests_passing=True."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="===== 5 passed in 0.3s =====\n",
            stderr="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "iteration": 0,
                "max_iterations": 5,
                "repo_path": tmpdir,
                "test_framework": "pytest",
                "package_manager": "pip",
                "language": "python",
            }
            result = self._run(_test_runner_node(state))

        assert result["iteration"] == 1
        assert result["all_tests_passing"] is True
        assert result["passed_tests"] == 5
        assert result["failed_tests"] == 0
        assert result["total_tests"] == 5

    @patch("app.agents.nodes.test_runner.run_tests")
    def test_some_failing(self, mock_run):
        """When tests fail, failures list is populated."""
        pytest_output = """
============================= FAILURES =============================
___________________________ test_add ___________________________

    def test_add():
>       assert add(1, 2) == 4
E       AssertionError: assert 3 == 4

src/calc.py:5: AssertionError
========================= 1 failed, 3 passed in 0.5s =========================
"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout=pytest_output,
            stderr="",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "iteration": 1,
                "max_iterations": 5,
                "repo_path": tmpdir,
                "test_framework": "pytest",
                "package_manager": "pip",
                "language": "python",
            }
            result = self._run(_test_runner_node(state))

        assert result["iteration"] == 2
        assert result["all_tests_passing"] is False
        assert result["failed_tests"] == 1
        assert result["passed_tests"] == 3
        assert len(result["failures"]) >= 1

    def test_missing_repo_path(self):
        """Missing repo_path returns error state."""
        state = {
            "iteration": 0,
            "max_iterations": 5,
            "repo_path": "/nonexistent/path",
            "test_framework": "pytest",
            "package_manager": "pip",
            "language": "python",
        }
        result = self._run(_test_runner_node(state))
        assert result["all_tests_passing"] is False
        assert result["failed_tests"] >= 1
        assert "error" in result


# ─── Parser unit tests ──────────────────────────────────────────

class TestParsePytestStdout:
    def test_all_pass(self):
        out = "===== 10 passed in 1.2s ====="
        p = _parse_pytest_stdout(out)
        assert p["total"] == 10
        assert p["passed"] == 10
        assert p["failed"] == 0

    def test_mixed(self):
        out = "===== 2 failed, 8 passed in 2.0s ====="
        p = _parse_pytest_stdout(out)
        assert p["total"] == 10
        assert p["passed"] == 8
        assert p["failed"] == 2

    def test_with_errors(self):
        out = "===== 1 failed, 1 error, 3 passed in 0.5s ====="
        p = _parse_pytest_stdout(out)
        assert p["failed"] == 2  # 1 failed + 1 error
        assert p["passed"] == 3

    def test_empty_output(self):
        p = _parse_pytest_stdout("")
        assert p["total"] == 0


class TestParseJestStdout:
    def test_jest_summary(self):
        out = "Tests:  2 failed, 5 passed, 7 total"
        p = _parse_jest_stdout(out)
        assert p["total"] == 7
        assert p["passed"] == 5
        assert p["failed"] == 2

    def test_all_pass(self):
        out = "Tests:  10 passed, 10 total"
        p = _parse_jest_stdout(out)
        assert p["total"] == 10
        assert p["passed"] == 10
        assert p["failed"] == 0
