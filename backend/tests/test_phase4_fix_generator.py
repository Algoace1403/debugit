"""
Phase 4 tests: fix_generator node with mocked Claude API.
"""
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.agents.nodes.fix_generator import fix_generator_node, _validate_diff


class TestFixGenerator:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_empty_classifications(self):
        """No classifications → empty proposed_fixes."""
        state = {"classifications": [], "repo_path": "/tmp", "iteration": 1, "failures": []}
        result = self._run(fix_generator_node(state))
        assert result["proposed_fixes"] == []

    @patch("app.agents.nodes.fix_generator.openai_service")
    def test_valid_diff_returned(self, mock_claude):
        """Classification with valid diff → proposed fix has diff populated."""
        valid_diff = (
            "--- a/src/calc.py\n"
            "+++ b/src/calc.py\n"
            "@@ -19,1 +19,1 @@\n"
            "-    if x > 10:\n"
            "+    if x >= 10:\n"
        )
        mock_claude.get_client.return_value = MagicMock()
        mock_claude.generate_fix = AsyncMock(return_value=valid_diff)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the source file
            src_dir = os.path.join(tmpdir, "src")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "calc.py"), "w") as f:
                f.write("def check(x):\n    if x > 10:\n        return True\n")

            state = {
                "classifications": [
                    {
                        "bug_type": "LOGIC",
                        "file": "src/calc.py",
                        "line": 19,
                        "fix_summary": "change > to >=",
                        "issue_line": "LOGIC error in src/calc.py line 19 → Fix: change > to >=",
                        "confidence": 0.85,
                        "root_cause": "off-by-one",
                        "method": "LLM",
                    }
                ],
                "repo_path": tmpdir,
                "iteration": 2,
                "failures": [],
            }
            result = self._run(fix_generator_node(state))

        assert len(result["proposed_fixes"]) == 1
        fix = result["proposed_fixes"][0]
        assert fix["file"] == "src/calc.py"
        assert fix["bug_type"] == "LOGIC"
        assert fix["iteration"] == 2
        assert "--- " in fix["diff"]
        assert "+++ " in fix["diff"]
        assert "generation_error" not in fix

    @patch("app.agents.nodes.fix_generator.openai_service")
    def test_invalid_diff_sets_error(self, mock_claude):
        """Claude returns garbage → diff="" and generation_error set."""
        mock_claude.get_client.return_value = MagicMock()
        mock_claude.generate_fix = AsyncMock(return_value="Here is the fixed file:\nprint('hello')\n")

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write("print('hello')\n")

            state = {
                "classifications": [
                    {
                        "bug_type": "SYNTAX",
                        "file": "main.py",
                        "line": 1,
                        "fix_summary": "fix syntax",
                        "issue_line": "SYNTAX error in main.py line 1 → Fix: fix syntax",
                        "confidence": 0.9,
                        "root_cause": "syntax error",
                        "method": "RULE",
                    }
                ],
                "repo_path": tmpdir,
                "iteration": 1,
                "failures": [],
            }
            result = self._run(fix_generator_node(state))

        fix = result["proposed_fixes"][0]
        assert fix["diff"] == ""
        assert "generation_error" in fix

    @patch("app.agents.nodes.fix_generator.openai_service")
    def test_missing_file_sets_error(self, mock_claude):
        """File doesn't exist → generation_error, no Claude call."""
        mock_claude.get_client.return_value = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            state = {
                "classifications": [
                    {
                        "bug_type": "LOGIC",
                        "file": "nonexistent.py",
                        "line": 5,
                        "fix_summary": "fix it",
                        "issue_line": "LOGIC error in nonexistent.py line 5 → Fix: fix it",
                        "confidence": 0.5,
                        "root_cause": "unknown",
                        "method": "LLM",
                    }
                ],
                "repo_path": tmpdir,
                "iteration": 1,
                "failures": [],
            }
            result = self._run(fix_generator_node(state))

        fix = result["proposed_fixes"][0]
        assert fix["diff"] == ""
        assert "generation_error" in fix
        # generate_fix should NOT have been called
        mock_claude.generate_fix.assert_not_called()

    @patch("app.agents.nodes.fix_generator.openai_service")
    def test_claude_exception_handled(self, mock_claude):
        """If Claude throws, diff="" and generation_error, no crash."""
        mock_claude.get_client.return_value = MagicMock()
        mock_claude.generate_fix = AsyncMock(side_effect=Exception("rate limited"))

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "app.py"), "w") as f:
                f.write("x = 1\n")

            state = {
                "classifications": [
                    {
                        "bug_type": "LOGIC",
                        "file": "app.py",
                        "line": 1,
                        "fix_summary": "fix",
                        "issue_line": "LOGIC error in app.py line 1 → Fix: fix",
                        "confidence": 0.7,
                        "root_cause": "error",
                        "method": "LLM",
                    }
                ],
                "repo_path": tmpdir,
                "iteration": 1,
                "failures": [],
            }
            result = self._run(fix_generator_node(state))

        fix = result["proposed_fixes"][0]
        assert fix["diff"] == ""
        assert "generation_error" in fix
        # When LLM fails and rule-based also can't fix, error reflects the fallback
        assert "generation_error" in fix


class TestValidateDiff:
    def test_valid(self):
        diff = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-old\n+new\n"
        assert _validate_diff(diff, "f.py", 10) is None

    def test_empty(self):
        assert _validate_diff("", "f.py", 10) is not None

    def test_no_header(self):
        assert _validate_diff("+++ b/f.py\n+new\n", "f.py", 10) is not None

    def test_no_plus_header(self):
        assert _validate_diff("--- a/f.py\n-old\n", "f.py", 10) is not None

    def test_too_large(self):
        lines = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n"
        lines += "".join(f"+line{i}\n" for i in range(250))
        assert _validate_diff(lines, "f.py", 500) is not None

    def test_large_ok_for_small_file(self):
        """Large diff is OK if file itself is tiny (<250 lines)."""
        lines = "--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n"
        lines += "".join(f"+line{i}\n" for i in range(210))
        assert _validate_diff(lines, "f.py", 100) is None
