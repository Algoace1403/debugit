"""
Phase 4 tests: bug_classifier node — rule-based and LLM fallback.
"""
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.agents.nodes.bug_classifier import bug_classifier_node


class TestBugClassifier:
    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_empty_failures(self):
        """No failures → empty classifications."""
        state = {"failures": [], "repo_path": "/tmp"}
        result = self._run(bug_classifier_node(state))
        assert result["classifications"] == []

    def test_rule_based_syntax_error(self):
        """SyntaxError is classified by rule, no LLM call."""
        state = {
            "failures": [
                {
                    "test_file": "tests/test_main.py",
                    "test_name": "test_main.py::test_parse",
                    "error_message": "SyntaxError: expected ':'",
                    "traceback": "File 'src/parser.py', line 10\n    SyntaxError: expected ':'",
                    "source_file": "src/parser.py",
                    "source_line": 10,
                }
            ],
            "repo_path": "/tmp",
        }
        result = self._run(bug_classifier_node(state))

        assert len(result["classifications"]) == 1
        c = result["classifications"][0]
        assert c["bug_type"] == "SYNTAX"
        assert c["method"] == "RULE"
        assert c["file"] == "src/parser.py"
        assert c["line"] == 10
        assert "SYNTAX error in src/parser.py line 10" in c["issue_line"]
        assert c["confidence"] == 0.9

    def test_rule_based_import_error(self):
        """ImportError classified by rule."""
        state = {
            "failures": [
                {
                    "test_file": "tests/test_app.py",
                    "test_name": "test_app.py::test_import",
                    "error_message": "ModuleNotFoundError: No module named 'requests'",
                    "traceback": "ModuleNotFoundError: No module named 'requests'",
                    "source_file": "src/app.py",
                    "source_line": 3,
                }
            ],
            "repo_path": "/tmp",
        }
        result = self._run(bug_classifier_node(state))

        c = result["classifications"][0]
        assert c["bug_type"] == "IMPORT"
        assert c["method"] == "RULE"
        assert "requests" in c["fix_summary"]

    @patch("app.agents.nodes.bug_classifier.openai_service")
    def test_llm_fallback_for_assertion_error(self, mock_claude):
        """AssertionError (not matched by rules) falls back to Claude."""
        mock_client = MagicMock()
        mock_claude.get_client.return_value = mock_client

        llm_json = json.dumps({
            "bug_type": "LOGIC",
            "confidence": 0.85,
            "root_cause": "off-by-one in boundary check",
            "affected_file": "src/calc.py",
            "affected_line": 19,
            "fix_summary": "change > to >= in boundary check",
        })
        mock_claude.classify_bug = AsyncMock(return_value=llm_json)

        state = {
            "failures": [
                {
                    "test_file": "tests/test_calc.py",
                    "test_name": "test_calc.py::test_boundary",
                    "error_message": "AssertionError: assert 5 == 6",
                    "traceback": "assert calc(5) == 6\nAssertionError",
                    "source_file": "src/calc.py",
                    "source_line": 19,
                }
            ],
            "repo_path": "/tmp",
        }
        result = self._run(bug_classifier_node(state))

        assert len(result["classifications"]) == 1
        c = result["classifications"][0]
        assert c["bug_type"] == "LOGIC"
        assert c["method"] == "LLM"
        assert c["file"] == "src/calc.py"
        assert c["line"] == 19
        assert c["confidence"] == 0.85
        assert "LOGIC error in src/calc.py line 19" in c["issue_line"]
        mock_claude.classify_bug.assert_awaited_once()

    @patch("app.agents.nodes.bug_classifier.openai_service")
    def test_llm_failure_falls_back_to_logic(self, mock_claude):
        """If LLM call throws, still produces a classification with low confidence."""
        mock_claude.get_client.return_value = MagicMock()
        mock_claude.classify_bug = AsyncMock(side_effect=Exception("API error"))

        state = {
            "failures": [
                {
                    "test_file": "tests/test_x.py",
                    "test_name": "test_x",
                    "error_message": "AssertionError",
                    "traceback": "assert False",
                    "source_file": "src/x.py",
                    "source_line": 5,
                }
            ],
            "repo_path": "/tmp",
        }
        result = self._run(bug_classifier_node(state))

        c = result["classifications"][0]
        assert c["bug_type"] == "LOGIC"
        assert c["confidence"] == 0.5  # rule-based fallback confidence
        assert c["method"] == "RULE_FALLBACK"

    def test_mixed_rule_and_no_source(self):
        """Multiple failures: one rule-matched, one without source_file uses test_file."""
        state = {
            "failures": [
                {
                    "test_file": "tests/test_a.py",
                    "test_name": "test_a",
                    "error_message": "TypeError: unsupported operand",
                    "traceback": "TypeError: unsupported operand",
                    "source_file": "",
                    "source_line": 0,
                },
                {
                    "test_file": "tests/test_b.py",
                    "test_name": "test_b",
                    "error_message": "IndentationError: unexpected indent",
                    "traceback": "IndentationError",
                    "source_file": "src/b.py",
                    "source_line": 7,
                },
            ],
            "repo_path": "/tmp",
        }
        result = self._run(bug_classifier_node(state))

        assert len(result["classifications"]) == 2
        # TypeError → rule
        assert result["classifications"][0]["bug_type"] == "TYPE_ERROR"
        assert result["classifications"][0]["file"] == "tests/test_a.py"
        # IndentationError → rule
        assert result["classifications"][1]["bug_type"] == "INDENTATION"
        assert result["classifications"][1]["file"] == "src/b.py"
