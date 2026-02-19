"""
Phase 6 tests: git_ops + ci_monitor wiring + results_builder consistency.
"""
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.agents.nodes.git_ops import git_ops_node
from app.agents.nodes.ci_monitor import ci_monitor_node
from app.services.results_builder import build_results


class TestGitOpsNode:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_no_fixed_files_skips_commit(self):
        """No fixes with status==fixed → last_commit_sha empty, total_commits unchanged."""
        state = {
            "iteration": 2,
            "repo_path": "/tmp/repo",
            "branch_name": "TEST_AI_Fix",
            "total_commits": 1,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LOGIC", "iteration": 2, "status": "failed"},
                {"file": "b.py", "bug_type": "SYNTAX", "iteration": 1, "status": "fixed"},
            ],
        }
        result = self._run(git_ops_node(state))

        assert result["last_commit_sha"] == ""
        assert "total_commits" not in result  # not incremented

    def test_fixed_files_from_wrong_iteration_skipped(self):
        """Fixes from iteration 1 are ignored when current iteration is 2."""
        state = {
            "iteration": 2,
            "repo_path": "/tmp/repo",
            "branch_name": "TEST_AI_Fix",
            "total_commits": 1,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "SYNTAX", "iteration": 1, "status": "fixed"},
            ],
        }
        result = self._run(git_ops_node(state))
        assert result["last_commit_sha"] == ""

    @patch("app.agents.nodes.git_ops.safe_commit_and_push")
    def test_fixed_files_triggers_commit(self, mock_commit):
        """Fixed files in current iteration → safe_commit_and_push called, sha stored."""
        mock_commit.return_value = "abc123def456"

        state = {
            "iteration": 1,
            "repo_path": "/tmp/repo",
            "branch_name": "TEAM_LEAD_AI_Fix",
            "total_commits": 0,
            "fixes_applied": [
                {"file": "src/calc.py", "bug_type": "LOGIC", "iteration": 1, "status": "fixed"},
                {"file": "src/util.py", "bug_type": "LINTING", "iteration": 1, "status": "fixed"},
                {"file": "src/bad.py", "bug_type": "SYNTAX", "iteration": 1, "status": "failed"},
            ],
        }
        result = self._run(git_ops_node(state))

        assert result["last_commit_sha"] == "abc123def456"
        assert result["total_commits"] == 1
        mock_commit.assert_called_once()
        call_args = mock_commit.call_args
        assert sorted(call_args.kwargs["fixed_files"]) == ["src/calc.py", "src/util.py"]
        assert set(call_args.kwargs["bug_types"]) == {"LOGIC", "LINTING"}

    @patch("app.agents.nodes.git_ops.safe_commit_and_push")
    def test_safe_commit_returns_none(self, mock_commit):
        """safe_commit_and_push returns None (no staged changes) → sha empty."""
        mock_commit.return_value = None

        state = {
            "iteration": 1,
            "repo_path": "/tmp/repo",
            "branch_name": "TEAM_LEAD_AI_Fix",
            "total_commits": 0,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LOGIC", "iteration": 1, "status": "fixed"},
            ],
        }
        result = self._run(git_ops_node(state))
        assert result["last_commit_sha"] == ""
        assert "total_commits" not in result  # not incremented

    @patch("app.agents.nodes.git_ops.safe_commit_and_push")
    def test_guardrail_error_sets_empty_sha(self, mock_commit):
        """RuntimeError from guardrail → sha empty, error set."""
        mock_commit.side_effect = RuntimeError("ABORT: missing _AI_Fix")

        state = {
            "iteration": 1,
            "repo_path": "/tmp/repo",
            "branch_name": "bad_branch",
            "total_commits": 0,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LOGIC", "iteration": 1, "status": "fixed"},
            ],
        }
        result = self._run(git_ops_node(state))
        assert result["last_commit_sha"] == ""
        assert "error" in result


class TestCIMonitorWiring:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_no_sha_local_only_passing(self):
        """No commit SHA → LOCAL_ONLY with local test status, no GitHub polling."""
        state = {
            "iteration": 1,
            "branch_name": "TEST_AI_Fix",
            "last_commit_sha": "",
            "all_tests_passing": True,
            "failed_tests": 0,
            "repo_url": "https://github.com/test/repo",
        }
        result = self._run(ci_monitor_node(state))

        assert result["ci_passed"] is True
        assert len(result["ci_runs"]) == 1
        ci_run = result["ci_runs"][0]
        assert ci_run["status"] == "PASSED"
        assert ci_run["mode"] == "LOCAL_ONLY"
        assert ci_run["run_url"] == ""
        assert ci_run["failures_remaining"] == 0

    def test_no_sha_local_only_failing(self):
        """No SHA + tests failing → LOCAL_ONLY FAILED."""
        state = {
            "iteration": 2,
            "branch_name": "TEST_AI_Fix",
            "last_commit_sha": "",
            "all_tests_passing": False,
            "failed_tests": 3,
            "repo_url": "https://github.com/test/repo",
        }
        result = self._run(ci_monitor_node(state))

        assert result["ci_passed"] is False
        ci_run = result["ci_runs"][0]
        assert ci_run["status"] == "FAILED"
        assert ci_run["mode"] == "LOCAL_ONLY"
        assert ci_run["failures_remaining"] == 3

    @patch("app.agents.nodes.ci_monitor._poll_github_actions")
    def test_with_sha_polls_github(self, mock_poll):
        """Valid commit SHA → GitHub Actions polling is called."""
        mock_poll.return_value = {
            "status": "PASSED",
            "mode": "CI",
            "run_url": "https://github.com/test/repo/actions/runs/123",
            "conclusion": "success",
        }

        state = {
            "iteration": 1,
            "branch_name": "TEST_AI_Fix",
            "last_commit_sha": "abc123",
            "all_tests_passing": True,
            "failed_tests": 0,
            "repo_url": "https://github.com/test/repo",
        }

        with patch("app.agents.nodes.ci_monitor.settings") as mock_settings:
            mock_settings.github_token = "ghp_test"
            result = self._run(ci_monitor_node(state))

        assert result["ci_passed"] is True
        ci_run = result["ci_runs"][0]
        assert ci_run["mode"] == "CI"
        assert ci_run["run_url"] == "https://github.com/test/repo/actions/runs/123"
        mock_poll.assert_awaited_once()

    @patch("app.agents.nodes.ci_monitor._poll_github_actions")
    def test_with_sha_poll_fails_fallback(self, mock_poll):
        """GitHub polling raises → falls back to LOCAL_ONLY."""
        mock_poll.side_effect = Exception("network error")

        state = {
            "iteration": 1,
            "branch_name": "TEST_AI_Fix",
            "last_commit_sha": "abc123",
            "all_tests_passing": False,
            "failed_tests": 2,
            "repo_url": "https://github.com/test/repo",
        }

        with patch("app.agents.nodes.ci_monitor.settings") as mock_settings:
            mock_settings.github_token = "ghp_test"
            result = self._run(ci_monitor_node(state))

        assert result["ci_passed"] is False
        ci_run = result["ci_runs"][0]
        assert ci_run["mode"] == "LOCAL_ONLY"


class TestResultsBuilderConsistency:
    def test_total_commits_reflects_actual(self):
        """total_commits in results matches state, not iteration count."""
        state = {
            "repo_url": "https://github.com/t/r",
            "team_name": "T",
            "leader_name": "L",
            "branch_name": "T_L_AI_Fix",
            "start_time": "2026-01-01T00:00:00",
            "end_time": "2026-01-01T00:05:00",
            "duration_seconds": 300,
            "total_commits": 2,  # only 2 real commits despite 3 iterations
            "failed_tests": 5,
            "all_tests_passing": True,
            "ci_passed": True,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LOGIC", "line_number": 1,
                 "issue_line": "x", "commit_message": "c", "status": "fixed",
                 "iteration": 1, "diff": "d"},
                {"file": "b.py", "bug_type": "SYNTAX", "line_number": 2,
                 "issue_line": "x", "commit_message": "c", "status": "fixed",
                 "iteration": 2, "diff": "d"},
                {"file": "c.py", "bug_type": "IMPORT", "line_number": 3,
                 "issue_line": "x", "commit_message": "c", "status": "failed",
                 "iteration": 3, "diff": ""},
            ],
            "ci_runs": [],
            "score": {"base": 100, "speed_bonus": 0, "efficiency_penalty": 0, "total": 100},
        }
        result = build_results(state)

        assert result["total_commits"] == 2
        assert result["total_fixes_applied"] == 2  # only "fixed" counted
        assert result["total_failures_detected"] == 5
        assert result["final_status"] == "PASSED"
        assert "github_token" not in json.dumps(result)

    def test_final_status_failed_when_not_passing(self):
        """final_status is FAILED when neither ci_passed nor all_tests_passing."""
        state = {
            "repo_url": "",
            "team_name": "",
            "leader_name": "",
            "branch_name": "",
            "start_time": "",
            "duration_seconds": 0,
            "total_commits": 1,
            "failed_tests": 2,
            "all_tests_passing": False,
            "ci_passed": False,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LOGIC", "line_number": 1,
                 "issue_line": "", "commit_message": "", "status": "fixed",
                 "iteration": 1, "diff": "d"},
            ],
            "ci_runs": [
                {"iteration": 1, "status": "FAILED", "mode": "LOCAL_ONLY",
                 "run_url": "", "timestamp": "", "failures_remaining": 2},
            ],
        }
        result = build_results(state)
        assert result["final_status"] == "FAILED"
        assert result["total_fixes_applied"] == 1
        assert result["total_commits"] == 1

    def test_local_only_pass_is_passed(self):
        """LOCAL_ONLY mode with all_tests_passing → final_status PASSED."""
        state = {
            "repo_url": "",
            "team_name": "",
            "leader_name": "",
            "branch_name": "",
            "start_time": "",
            "duration_seconds": 100,
            "total_commits": 1,
            "failed_tests": 0,
            "all_tests_passing": True,
            "ci_passed": False,  # no CI, but local tests pass
            "fixes_applied": [],
            "ci_runs": [
                {"iteration": 1, "status": "PASSED", "mode": "LOCAL_ONLY",
                 "run_url": "", "timestamp": "", "failures_remaining": 0},
            ],
        }
        result = build_results(state)
        assert result["final_status"] == "PASSED"
