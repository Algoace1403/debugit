import json
import os
import re

from app.models.state import HealingState
from app.services.parsers import classify_from_traceback
from app.services.scoring import format_issue_line
from app.services import openai_service
from app.utils.logger import get_logger

logger = get_logger("bug_classifier")


async def bug_classifier_node(state: HealingState) -> dict:
    """
    Classify each test failure: rule-based first, Claude LLM fallback.
    Produces a list of Classification dicts for downstream fix_generator.
    """
    failures = state.get("failures", [])
    repo_path = state.get("repo_path", "")

    if not failures:
        logger.info("No failures to classify")
        return {
            "classifications": [],
            "current_node": "bug_classifier",
            "status_message": "No failures to classify",
        }

    logger.info(f"=== BUG CLASSIFIER: {len(failures)} failures to classify ===")
    for i, f in enumerate(failures):
        logger.info(f"  Failure {i+1}: file={f.get('source_file','?')}, "
                     f"line={f.get('source_line',0)}, "
                     f"error={f.get('error_message','')[:100]}")

    classifications = []
    client = None  # lazy-init only if LLM needed

    for failure in failures:
        error_msg = failure.get("error_message", "")
        traceback_str = failure.get("traceback", "")
        source_file = failure.get("source_file", "")
        source_line = failure.get("source_line", 0)

        # Step 1: Try rule-based classification
        rule_result = classify_from_traceback(error_msg, traceback_str)

        if rule_result is not None:
            bug_type, fix_summary = rule_result
            classification = _build_classification(
                bug_type=bug_type,
                file=source_file or failure.get("test_file", ""),
                line=source_line,
                fix_summary=fix_summary,
                confidence=0.9,
                root_cause=error_msg[:200],
                method="RULE",
            )
            classifications.append(classification)
            logger.info(f"RULE: {classification['issue_line']}")
            continue

        # Step 2: LLM fallback
        try:
            if client is None:
                client = openai_service.get_client()

            source_code = _read_source_file(repo_path, source_file)
            llm_response = await openai_service.classify_bug(client, failure, source_code)
            parsed = _parse_llm_response(llm_response)

            bug_type = parsed.get("bug_type", "LOGIC")
            # Validate bug_type
            if bug_type not in ("LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION"):
                bug_type = "LOGIC"

            classification = _build_classification(
                bug_type=bug_type,
                file=parsed.get("affected_file", source_file or failure.get("test_file", "")),
                line=parsed.get("affected_line", source_line),
                fix_summary=parsed.get("fix_summary", "fix the logic error"),
                confidence=parsed.get("confidence", 0.7),
                root_cause=parsed.get("root_cause", error_msg[:200]),
                method="LLM",
            )
            classifications.append(classification)
            logger.info(f"LLM: {classification['issue_line']}")

        except Exception as e:
            logger.warning(f"LLM classification failed for {source_file}: {e}")
            # Fallback: extract info from traceback and classify as LOGIC
            fb = _classify_from_assertion(failure, repo_path)
            classification = _build_classification(
                bug_type=fb.get("bug_type", "LOGIC"),
                file=fb.get("file", source_file or failure.get("test_file", "")),
                line=fb.get("line", source_line),
                fix_summary=fb.get("fix_summary", "fix the logic error"),
                confidence=0.5,
                root_cause=fb.get("root_cause", f"LLM failed: {e}"),
                method="RULE_FALLBACK",
            )
            classifications.append(classification)
            logger.info(f"RULE_FALLBACK: {classification['issue_line']}")

    rule_count = sum(1 for c in classifications if c["method"] == "RULE")
    llm_count = len(classifications) - rule_count

    logger.info(f"=== BUG CLASSIFIER DONE: {len(classifications)} classified "
                f"({rule_count} rule, {llm_count} LLM) ===")
    for c in classifications:
        logger.info(f"  → {c['issue_line']} (method={c['method']}, confidence={c['confidence']})")

    return {
        "classifications": classifications,
        "current_node": "bug_classifier",
        "status_message": f"Classified {len(classifications)} bugs ({rule_count} rule, {llm_count} LLM)",
    }


def _build_classification(
    bug_type: str,
    file: str,
    line: int,
    fix_summary: str,
    confidence: float,
    root_cause: str,
    method: str,
) -> dict:
    """Build a Classification dict with canonical issue_line."""
    issue_line = format_issue_line(bug_type, file or "unknown", line, fix_summary)
    return {
        "bug_type": bug_type,
        "file": file or "unknown",
        "line": line,
        "fix_summary": fix_summary,
        "issue_line": issue_line,
        "confidence": confidence,
        "root_cause": root_cause,
        "method": method,
    }


def _read_source_file(repo_path: str, relative_path: str) -> str:
    """Read source file content for LLM context. Returns empty string on failure."""
    if not repo_path or not relative_path:
        return ""
    full_path = os.path.join(repo_path, relative_path)
    try:
        with open(full_path) as f:
            lines = f.readlines()
        # Add line numbers for LLM context
        return "".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
    except OSError:
        return ""


def _parse_llm_response(raw: str) -> dict:
    """Parse Claude's JSON response, handling markdown code fences."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _classify_from_assertion(failure: dict, repo_path: str) -> dict:
    """
    When LLM is unavailable, extract classification from test failure info.
    Analyzes assertion errors, traceback patterns, and error messages
    to determine bug type, file, and line.
    """
    error_msg = failure.get("error_message", "")
    traceback_str = failure.get("traceback", "")
    source_file = failure.get("source_file", "")
    source_line = failure.get("source_line", 0)
    combined = error_msg + "\n" + traceback_str

    result: dict = {
        "bug_type": "LOGIC",
        "file": source_file,
        "line": source_line,
        "fix_summary": "fix the logic error",
        "root_cause": "",
    }

    # Try to extract file:line from traceback if not already known
    if not source_file or source_file == "unknown":
        # Pattern: "file.py:NN: ErrorType"
        loc_match = re.search(r'(\S+\.py):(\d+):\s+(\w+)', combined)
        if loc_match:
            result["file"] = loc_match.group(1)
            result["line"] = int(loc_match.group(2))
        else:
            # Pattern: 'File "path/file.py", line N'
            file_match = re.search(r'File\s+"([^"]+\.py)",\s+line\s+(\d+)', combined)
            if file_match:
                path = file_match.group(1)
                # Make relative to repo_path if possible
                if repo_path and path.startswith(repo_path):
                    path = os.path.relpath(path, repo_path)
                result["file"] = path
                result["line"] = int(file_match.group(2))

    # ZeroDivisionError
    if "ZeroDivisionError" in combined:
        result["bug_type"] = "LOGIC"
        result["fix_summary"] = "add zero-division guard"
        result["root_cause"] = "Division by zero not handled"
        return result

    # AssertionError with numeric mismatch → operator swap
    assert_match = re.search(r'assert\s+(-?\d+)\s*==\s*(-?\d+)', combined)
    if assert_match:
        actual = assert_match.group(1)
        expected = assert_match.group(2)
        result["bug_type"] = "LOGIC"
        result["fix_summary"] = "fix arithmetic operator"
        result["root_cause"] = f"Got {actual} but expected {expected} — likely wrong operator"

        # Try to find the function and its file from "where X = func(...)"
        where_match = re.search(r'where\s+.*?=\s*(\w+)\(', combined)
        if where_match:
            func_name = where_match.group(1)
            # Search for the function definition in repo
            func_file, func_line = _find_function_def(repo_path, func_name, result.get("file", ""))
            if func_file:
                result["file"] = func_file
            if func_line:
                result["line"] = func_line
        return result

    # TypeError
    if "TypeError" in combined:
        result["bug_type"] = "TYPE_ERROR"
        result["fix_summary"] = "fix the type mismatch"
        result["root_cause"] = error_msg[:200]
        return result

    # NameError
    if "NameError" in combined:
        name_match = re.search(r"name '(\w+)' is not defined", combined)
        if name_match:
            result["bug_type"] = "IMPORT"
            result["fix_summary"] = f"fix reference to '{name_match.group(1)}'"
            result["root_cause"] = f"Undefined name: {name_match.group(1)}"
        return result

    # Generic assertion failure — likely LOGIC
    if "AssertionError" in combined or "assert " in combined:
        result["bug_type"] = "LOGIC"
        result["fix_summary"] = "fix the logic error"
        result["root_cause"] = error_msg[:200]

    return result


def _find_function_def(repo_path: str, func_name: str, hint_file: str) -> tuple[str, int]:
    """
    Find where a function is defined.
    Returns (relative_file_path, line_number) or ("", 0) if not found.
    """
    import glob as glob_mod

    # First try the hint file
    files_to_check = []
    if hint_file:
        files_to_check.append(hint_file)

    # Then scan all Python files
    if repo_path:
        for path in glob_mod.glob(os.path.join(repo_path, "**/*.py"), recursive=True):
            rel = os.path.relpath(path, repo_path)
            if rel not in files_to_check and "__pycache__" not in rel:
                files_to_check.append(rel)

    pattern = re.compile(rf'def\s+{re.escape(func_name)}\s*\(')

    for file_rel in files_to_check:
        full_path = os.path.join(repo_path, file_rel) if repo_path else file_rel
        try:
            with open(full_path) as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        return file_rel, i
        except OSError:
            continue

    return "", 0
