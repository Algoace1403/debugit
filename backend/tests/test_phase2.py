"""
Phase 2 tests: branch naming, git guardrails, results redaction,
scoring, results builder, and API integration.
"""
import asyncio
import json
import os
import subprocess
import tempfile
from unittest.mock import patch, MagicMock

import pytest


# ─── Branch Naming ───────────────────────────────────────────────
from app.services.github_service import make_branch_name


class TestBranchNaming:
    def test_spec_example_1(self):
        assert make_branch_name("RIFT ORGANISERS", "Saiyam Kumar") == "RIFT_ORGANISERS_SAIYAM_KUMAR_AI_Fix"

    def test_spec_example_2(self):
        assert make_branch_name("Code Warriors", "John Doe") == "CODE_WARRIORS_JOHN_DOE_AI_Fix"

    def test_special_chars(self):
        assert make_branch_name("Team--Alpha!!", "Jane O'Brien") == "TEAM_ALPHA_JANE_OBRIEN_AI_Fix"

    def test_extra_spaces(self):
        assert make_branch_name("  spaced  out  ", " name ") == "SPACED_OUT_NAME_AI_Fix"

    def test_suffix_exact_casing(self):
        result = make_branch_name("Test", "User")
        assert result.endswith("_AI_Fix")
        assert not result.endswith("_AI_FIX")
        assert not result.endswith("_ai_fix")

    def test_numeric_in_name(self):
        assert make_branch_name("Team 42", "Agent 007") == "TEAM_42_AGENT_007_AI_Fix"


# ─── Git Guardrails (mocked subprocess) ─────────────────────────
from app.services.github_service import safe_commit_and_push


class TestGitGuardrails:
    def test_empty_files_returns_none(self):
        """No files to commit → returns None immediately, no git calls."""
        result = safe_commit_and_push("/fake", "TEST_AI_Fix", 1, ["LINTING"], [])
        assert result is None

    def test_missing_suffix_aborts(self):
        """Branch not ending with _AI_Fix → RuntimeError before any git call."""
        with pytest.raises(RuntimeError, match="_AI_Fix"):
            safe_commit_and_push("/fake", "bad_branch", 1, ["LINTING"], ["file.py"])

    def test_main_branch_aborts(self):
        """If branch_name is main → blocked by suffix check (main doesn't end with _AI_Fix)."""
        with pytest.raises(RuntimeError, match="ABORT"):
            safe_commit_and_push("/fake", "main", 1, ["LINTING"], ["file.py"])

    def test_wrong_branch_aborts(self):
        """If current git branch != expected → RuntimeError."""
        with patch("app.services.github_service.subprocess") as mock_sub:
            mock_sub.check_output.return_value = b"wrong_branch\n"
            with pytest.raises(RuntimeError, match="ABORT.*expected"):
                safe_commit_and_push("/fake", "TEST_AI_Fix", 1, ["LINTING"], ["file.py"])


# ─── Redaction ───────────────────────────────────────────────────
from app.services.github_service import redact_state


class TestRedaction:
    def test_removes_github_token(self):
        state = {"repo_url": "https://example.com", "github_token": "ghp_secret123", "team_name": "Test"}
        safe = redact_state(state)
        assert "github_token" not in safe
        assert safe["repo_url"] == "https://example.com"
        assert safe["team_name"] == "Test"

    def test_no_token_still_works(self):
        state = {"repo_url": "https://example.com"}
        safe = redact_state(state)
        assert safe == state


# ─── Results Builder ─────────────────────────────────────────────
from app.services.results_builder import build_results


class TestResultsBuilder:
    def test_basic_build(self):
        state = {
            "repo_url": "https://github.com/test/repo",
            "team_name": "RIFT",
            "leader_name": "Saiyam",
            "branch_name": "RIFT_SAIYAM_AI_Fix",
            "start_time": "2026-01-01T00:00:00",
            "end_time": "2026-01-01T00:04:00",
            "duration_seconds": 240,
            "total_commits": 2,
            "failed_tests": 3,
            "all_tests_passing": True,
            "ci_passed": True,
            "fixes_applied": [
                {"file": "a.py", "bug_type": "LINTING", "line_number": 5,
                 "issue_line": "LINTING error in a.py line 5 → Fix: remove import",
                 "commit_message": "[AI-AGENT] ...", "status": "fixed",
                 "iteration": 1, "diff": ""},
                {"file": "b.py", "bug_type": "SYNTAX", "line_number": 10,
                 "issue_line": "SYNTAX error in b.py line 10 → Fix: add colon",
                 "commit_message": "[AI-AGENT] ...", "status": "failed",
                 "iteration": 1, "diff": ""},
            ],
            "ci_runs": [
                {"iteration": 1, "status": "FAILED", "mode": "CI",
                 "run_url": "https://...", "timestamp": "2026-01-01T00:02:00",
                 "failures_remaining": 1},
            ],
            "github_token": "ghp_SECRET",
        }
        result = build_results(state)

        # Token NEVER in results
        assert "github_token" not in json.dumps(result)

        # Schema correctness
        assert result["final_status"] == "PASSED"
        assert result["total_fixes_applied"] == 1  # only 1 "fixed"
        assert result["total_failures_detected"] == 3
        assert result["total_commits"] == 2
        assert len(result["fixes"]) == 2
        assert len(result["ci_runs"]) == 1
        assert result["score"]["speed_bonus"] == 10  # < 300s
        assert result["branch_name"] == "RIFT_SAIYAM_AI_Fix"

    def test_empty_state(self):
        result = build_results({})
        assert result["final_status"] == "FAILED"
        assert result["fixes"] == []
        assert result["ci_runs"] == []
        assert "github_token" not in json.dumps(result)


# ─── Scoring ─────────────────────────────────────────────────────
from app.services.scoring import calculate_score, format_issue_line


class TestScoring:
    def test_fast_few_commits(self):
        s = calculate_score(200, 3)
        assert s["total"] == 110
        assert s["speed_bonus"] == 10
        assert s["efficiency_penalty"] == 0

    def test_slow_many_commits(self):
        s = calculate_score(400, 25)
        assert s["total"] == 90
        assert s["speed_bonus"] == 0
        assert s["efficiency_penalty"] == 10

    def test_floor_at_zero(self):
        s = calculate_score(999, 100)
        assert s["total"] == 0  # max(0, 100 + 0 - 160)

    def test_format_issue_line(self):
        line = format_issue_line("LINTING", "src/utils.py", 15, "remove the import statement")
        assert line == "LINTING error in src/utils.py line 15 → Fix: remove the import statement"

    def test_format_issue_line_bad_type(self):
        with pytest.raises(AssertionError):
            format_issue_line("INVALID", "file.py", 1, "fix")


# ─── URL Parsing ─────────────────────────────────────────────────
from app.services.github_service import parse_github_url


class TestParseGithubUrl:
    def test_normal_url(self):
        assert parse_github_url("https://github.com/owner/repo") == ("owner", "repo")

    def test_dot_git_url(self):
        assert parse_github_url("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_invalid_url(self):
        with pytest.raises(ValueError):
            parse_github_url("https://gitlab.com/owner/repo")


# ─── Run Store (async) ──────────────────────────────────────────
from app.services.run_store import RunStore


class TestRunStore:
    def test_create_and_read(self):
        store = RunStore()
        # Override data dir to temp
        store._data_dir = __import__("pathlib").Path(tempfile.mkdtemp())

        loop = asyncio.new_event_loop()

        state = {"repo_url": "https://test.com", "status": "running"}
        loop.run_until_complete(store.create("test-123", state))

        read_back = loop.run_until_complete(store.get_state("test-123"))
        assert read_back["repo_url"] == "https://test.com"

        # Update
        loop.run_until_complete(store.update_state("test-123", {"iteration": 2}))
        read_back = loop.run_until_complete(store.get_state("test-123"))
        assert read_back["iteration"] == 2

        # Results
        loop.run_until_complete(store.save_results("test-123", {"score": 100}))
        results = loop.run_until_complete(store.get_results("test-123"))
        assert results["score"] == 100

        # List
        runs = loop.run_until_complete(store.list_runs())
        assert len(runs) == 1
        assert runs[0]["run_id"] == "test-123"

        loop.close()

    def test_nonexistent_run(self):
        store = RunStore()
        store._data_dir = __import__("pathlib").Path(tempfile.mkdtemp())
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(store.get_state("nope"))
        assert result is None
        loop.close()


# ─── API Integration (FastAPI TestClient) ────────────────────────
from fastapi.testclient import TestClient
from app.main import app


class TestAPI:
    def setup_method(self):
        self.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_heal_returns_run_id(self):
        r = self.client.post("/api/v1/heal", json={
            "repo_url": "https://github.com/test/repo",
            "team_name": "Test Team",
            "leader_name": "Test Leader",
        })
        assert r.status_code == 200
        data = r.json()
        assert "run_id" in data
        assert data["status"] == "running"
        # run_id should be a valid UUID
        import uuid
        uuid.UUID(data["run_id"])  # raises if invalid

    def test_heal_missing_field_422(self):
        r = self.client.post("/api/v1/heal", json={"repo_url": "https://github.com/test/repo"})
        assert r.status_code == 422

    def test_run_not_found(self):
        r = self.client.get("/api/v1/runs/nonexistent-id")
        assert r.status_code == 404

    def test_runs_list(self):
        r = self.client.get("/api/v1/runs")
        assert r.status_code == 200
        assert "runs" in r.json()
