import json
import os
import re

from app.models.state import HealingState
from app.services.sandbox import run_tests
from app.utils.framework_detector import get_test_command
from app.utils.logger import get_logger

logger = get_logger("test_runner")


async def test_runner_node(state: HealingState) -> dict:
    """
    Run tests in sandbox, parse results, extract failures.
    Increments iteration each time it runs.
    """
    iteration = state.get("iteration", 0) + 1
    max_iter = state.get("max_iterations", 5)
    repo_path = state.get("repo_path", "")
    test_framework = state.get("test_framework", "pytest")
    package_manager = state.get("package_manager", "pip")
    language = state.get("language", "python")
    test_files = state.get("test_files", [])

    logger.info(f"=== TEST RUNNER: iteration {iteration}/{max_iter}, "
                f"framework={test_framework}, pkg={package_manager}, lang={language}, "
                f"test_files={test_files} ===")

    # If repo_path is missing or doesn't exist, return error
    if not repo_path or not os.path.isdir(repo_path):
        logger.error(f"repo_path missing or invalid: {repo_path}")
        return _error_result(
            iteration, max_iter,
            f"repo_path missing or invalid: {repo_path}",
        )

    # Get the test command (pass test_files so pytest discovers non-standard filenames)
    test_cmd = get_test_command(test_framework, package_manager, test_files)
    logger.info(f"Test command: {test_cmd}")

    try:
        result = run_tests(repo_path, test_cmd)
    except Exception as e:
        logger.error(f"Test execution crashed: {e}")
        return _error_result(iteration, max_iter, f"Test execution failed: {e}")

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = stdout + "\n" + stderr

    logger.info(f"Test exit code: {result.returncode}, stdout={len(stdout)} chars")

    # Try structured parsing first, then fall back to regex
    report_path = os.path.join(repo_path, "report.json")
    parsed = None

    if test_framework in ("pytest", "unittest") and os.path.isfile(report_path):
        parsed = _parse_pytest_json_report(report_path)
    elif test_framework in ("jest", "vitest") and os.path.isfile(report_path):
        parsed = _parse_jest_json_report(report_path)

    if parsed is None:
        if language in ("python", "mixed") or test_framework in ("pytest", "unittest"):
            parsed = _parse_pytest_stdout(combined)
        else:
            parsed = _parse_jest_stdout(combined)

    total_tests = parsed["total"]
    passed_tests = parsed["passed"]
    failed_tests = parsed["failed"]
    failures = parsed["failures"]
    all_passing = failed_tests == 0 and total_tests > 0

    # If the command itself failed but we parsed 0 tests, synthesize a failure
    if result.returncode != 0 and total_tests == 0:
        failed_tests = 1
        all_passing = False
        failures = [_synthetic_failure(combined)]

    logger.info(f"=== TEST RUNNER DONE: {passed_tests}/{total_tests} passed, "
                f"{failed_tests} failed, all_passing={all_passing} ===")
    for i, f in enumerate(failures[:5]):  # limit to first 5 for readability
        logger.info(f"  Failure {i+1}: {f.get('test_name','?')} — "
                     f"file={f.get('source_file','?')}, "
                     f"error={f.get('error_message','')[:100]}")

    return {
        "iteration": iteration,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "failures": failures,
        "all_tests_passing": all_passing,
        "current_node": "test_runner",
        "status_message": (
            f"Iteration {iteration}/{max_iter}: "
            f"{passed_tests}/{total_tests} passed"
            + (" - ALL PASS" if all_passing else f" - {failed_tests} FAILED")
        ),
    }


def _error_result(iteration: int, max_iter: int, msg: str) -> dict:
    return {
        "iteration": iteration,
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 1,
        "failures": [_synthetic_failure(msg)],
        "all_tests_passing": False,
        "current_node": "test_runner",
        "status_message": f"Iteration {iteration}/{max_iter}: ERROR - {msg}",
        "error": msg,
    }


def _synthetic_failure(output: str) -> dict:
    """Create a synthetic TestFailure when we can't parse real ones."""
    return {
        "test_file": "",
        "test_name": "test_execution",
        "error_message": output[:500],
        "traceback": output[:2000],
        "source_file": "",
        "source_line": 0,
    }


# ── Pytest JSON report parsing ──────────────────────────────────

def _parse_pytest_json_report(report_path: str) -> dict | None:
    """Parse pytest-json-report output."""
    try:
        with open(report_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    summary = data.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0) + summary.get("error", 0)

    failures = []
    for test in data.get("tests", []):
        if test.get("outcome") in ("failed", "error"):
            call = test.get("call", {}) or test.get("setup", {}) or {}
            crash = call.get("crash", {})
            tb = call.get("longrepr", "")

            failures.append({
                "test_file": test.get("nodeid", "").split("::")[0],
                "test_name": test.get("nodeid", ""),
                "error_message": crash.get("message", "")[:500],
                "traceback": tb[:2000] if isinstance(tb, str) else str(tb)[:2000],
                "source_file": crash.get("path", ""),
                "source_line": crash.get("lineno", 0),
            })

    return {"total": total, "passed": passed, "failed": failed, "failures": failures}


# ── Pytest stdout parsing ────────────────────────────────────────

def _parse_pytest_stdout(output: str) -> dict:
    """Parse pytest verbose stdout for pass/fail counts and failure info."""
    total = 0
    passed = 0
    failed = 0
    failures = []

    # Look for summary line: "= X passed, Y failed ="  or "= X passed ="
    # Must contain "passed" or "failed" to distinguish from "= FAILURES ="
    summary_match = re.search(
        r"=+\s*((?:.*?\d+\s+(?:passed|failed).*?))\s*=+\s*$", output, re.MULTILINE
    )
    if summary_match:
        summary_text = summary_match.group(1)
        p = re.search(r"(\d+)\s+passed", summary_text)
        f = re.search(r"(\d+)\s+failed", summary_text)
        e = re.search(r"(\d+)\s+error", summary_text)
        if p:
            passed = int(p.group(1))
        if f:
            failed = int(f.group(1))
        if e:
            failed += int(e.group(1))
        total = passed + failed

    # Extract FAILURES section
    failures_section = re.search(
        r"=+ FAILURES =+\n(.*?)(?==+|$)", output, re.DOTALL
    )
    if failures_section:
        # Split individual test failures by the "___ test_name ___" separator
        blocks = re.split(r"_+ ([\w:./<>\[\]]+) _+", failures_section.group(1))
        # blocks alternates: [pre, test_name, content, test_name, content, ...]
        i = 1
        while i < len(blocks) - 1:
            test_name = blocks[i]
            content = blocks[i + 1]

            # Try to extract source file and line from traceback
            source_file = ""
            source_line = 0
            error_message = ""

            # Match "file.py:NN: ErrorType" pattern
            loc_match = re.search(r"(\S+\.py):(\d+):\s+(\w+Error.*)", content)
            if loc_match:
                source_file = loc_match.group(1)
                source_line = int(loc_match.group(2))
                error_message = loc_match.group(3)

            # Also try "E   ErrorType: message" lines
            if not error_message:
                e_match = re.search(r"^E\s+(.+)$", content, re.MULTILINE)
                if e_match:
                    error_message = e_match.group(1)

            test_file = test_name.split("::")[0] if "::" in test_name else ""

            failures.append({
                "test_file": test_file,
                "test_name": test_name,
                "error_message": error_message[:500],
                "traceback": content[:2000],
                "source_file": source_file,
                "source_line": source_line,
            })
            i += 2

    # If we found failures in the section but didn't match summary counts,
    # use the failure list length
    if failures and failed == 0:
        failed = len(failures)
        total = passed + failed

    return {"total": total, "passed": passed, "failed": failed, "failures": failures}


# ── Jest/Vitest JSON report parsing ─────────────────────────────

def _parse_jest_json_report(report_path: str) -> dict | None:
    """Parse Jest/Vitest JSON output."""
    try:
        with open(report_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    total = data.get("numTotalTests", 0)
    passed = data.get("numPassedTests", 0)
    failed = data.get("numFailedTests", 0)

    failures = []
    for suite in data.get("testResults", []):
        for test in suite.get("assertionResults", []):
            if test.get("status") == "failed":
                msgs = test.get("failureMessages", [])
                tb = "\n".join(msgs) if msgs else ""

                # Try to extract source file/line from failure message
                source_file = suite.get("name", "")
                source_line = 0
                loc_match = re.search(r"at.*?\((.+?):(\d+):\d+\)", tb)
                if loc_match:
                    source_file = loc_match.group(1)
                    source_line = int(loc_match.group(2))

                failures.append({
                    "test_file": suite.get("name", ""),
                    "test_name": " > ".join(test.get("ancestorTitles", []) + [test.get("title", "")]),
                    "error_message": (msgs[0][:500] if msgs else ""),
                    "traceback": tb[:2000],
                    "source_file": source_file,
                    "source_line": source_line,
                })

    return {"total": total, "passed": passed, "failed": failed, "failures": failures}


# ── Jest/Vitest stdout parsing ───────────────────────────────────

def _parse_jest_stdout(output: str) -> dict:
    """Parse Jest/Vitest/Mocha verbose stdout."""
    total = 0
    passed = 0
    failed = 0
    failures = []

    # Jest summary: "Tests: X failed, Y passed, Z total"
    jest_summary = re.search(r"Tests:\s+(?:(\d+)\s+failed,\s*)?(\d+)\s+passed,\s+(\d+)\s+total", output)
    if jest_summary:
        failed = int(jest_summary.group(1) or 0)
        passed = int(jest_summary.group(2))
        total = int(jest_summary.group(3))

    # Vitest summary: "X passed | Y failed" or "Tests  X passed | Y failed (Z)"
    if total == 0:
        vitest_match = re.search(r"(\d+)\s+passed.*?(\d+)\s+failed", output)
        if vitest_match:
            passed = int(vitest_match.group(1))
            failed = int(vitest_match.group(2))
            total = passed + failed

    # Mocha summary: "N passing" / "N failing"
    if total == 0:
        mocha_p = re.search(r"(\d+)\s+passing", output)
        mocha_f = re.search(r"(\d+)\s+failing", output)
        if mocha_p:
            passed = int(mocha_p.group(1))
        if mocha_f:
            failed = int(mocha_f.group(1))
        total = passed + failed

    # Extract FAIL lines for Jest: "FAIL src/file.test.js"
    fail_blocks = re.findall(r"FAIL\s+(\S+)", output)
    for fb in fail_blocks:
        if not any(f["test_file"] == fb for f in failures):
            failures.append({
                "test_file": fb,
                "test_name": fb,
                "error_message": f"Test suite failed: {fb}",
                "traceback": "",
                "source_file": fb,
                "source_line": 0,
            })

    return {"total": total, "passed": passed, "failed": failed, "failures": failures}
