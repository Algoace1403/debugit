import os

from app.models.state import HealingState
from app.services import openai_service
from app.services.rule_fixer import generate_rule_based_fix
from app.utils.logger import get_logger

logger = get_logger("fix_generator")


async def fix_generator_node(state: HealingState) -> dict:
    """
    For each classification, ask OpenAI for a unified diff patch.
    If OpenAI fails or is unavailable, fall back to rule-based fix generation.
    Outputs proposed_fixes list for fix_validator to apply and test.
    Does NOT apply patches or mark status.
    """
    classifications = state.get("classifications", [])
    repo_path = state.get("repo_path", "")
    iteration = state.get("iteration", 0)
    failures = state.get("failures", [])

    if not classifications:
        logger.info("No classifications to fix")
        return {
            "proposed_fixes": [],
            "current_node": "fix_generator",
            "status_message": "No classifications to generate fixes for",
        }

    logger.info(f"=== FIX GENERATOR: {len(classifications)} classifications ===")
    for i, c in enumerate(classifications):
        logger.info(f"  Classification {i+1}: {c.get('bug_type','?')} in {c.get('file','?')} "
                     f"line {c.get('line',0)} — {c.get('fix_summary','')}")

    # Try to get OpenAI client — may fail if API key missing/invalid
    client = None
    llm_available = True
    try:
        client = openai_service.get_client()
    except Exception as e:
        logger.warning(f"OpenAI client init failed, using rule-based fallback only: {e}")
        llm_available = False

    proposed_fixes = []

    for cls in classifications:
        file_rel = cls.get("file", "")
        bug_type = cls.get("bug_type", "LOGIC")
        line = cls.get("line", 0)
        issue_line = cls.get("issue_line", "")

        fix_entry = {
            "file": file_rel,
            "bug_type": bug_type,
            "line_number": line,
            "issue_line": issue_line,
            "diff": "",
            "iteration": iteration,
        }

        # Read the target file
        file_content, file_lines = _read_file_with_numbers(repo_path, file_rel)
        if not file_content:
            logger.warning(f"Cannot read {file_rel}, skipping")
            fix_entry["generation_error"] = f"Cannot read file: {file_rel}"
            proposed_fixes.append(fix_entry)
            continue

        # Find matching failure for error context
        failure = _find_matching_failure_dict(failures, file_rel, line)
        error_info = _format_failure(failure) if failure else ""

        # ── Strategy 1: Claude LLM ───────────────────────────
        llm_succeeded = False
        if llm_available and client is not None:
            try:
                raw_diff = await openai_service.generate_fix(
                    client, cls, file_content, error_info,
                )
                diff = _extract_diff(raw_diff)
                error = _validate_diff(diff, file_rel, file_lines)
                if error:
                    logger.warning(f"Invalid LLM diff for {file_rel}: {error}")
                else:
                    fix_entry["diff"] = diff
                    fix_entry["method"] = "LLM"
                    llm_succeeded = True
                    logger.info(f"LLM generated diff for {file_rel} ({len(diff)} chars)")
            except Exception as e:
                logger.warning(f"OpenAI generate_fix failed for {file_rel}: {e}")
                # Mark LLM as unavailable for remaining classifications
                # (likely a billing/auth issue affecting all calls)
                if "credit balance" in str(e).lower() or "401" in str(e) or "403" in str(e):
                    llm_available = False
                    logger.warning("LLM unavailable (billing/auth) — switching to rule-based fallback for all remaining")

        # ── Strategy 2: Rule-based fallback ──────────────────
        if not llm_succeeded:
            logger.info(f"FALLBACK: Attempting rule-based fix for {file_rel} ({bug_type})")
            rule_diff = generate_rule_based_fix(repo_path, cls, failure)
            if rule_diff:
                error = _validate_diff(rule_diff, file_rel, file_lines)
                if error:
                    logger.warning(f"Invalid rule-based diff for {file_rel}: {error}")
                    fix_entry["generation_error"] = f"Rule-based diff invalid: {error}"
                else:
                    fix_entry["diff"] = rule_diff
                    fix_entry["method"] = "RULE"
                    logger.info(f"FALLBACK: Rule-based diff for {file_rel} ({len(rule_diff)} chars)")
            else:
                fix_entry["generation_error"] = "LLM unavailable and no rule-based fix found"
                logger.info(f"FALLBACK: No rule-based fix possible for {file_rel} ({bug_type})")

        proposed_fixes.append(fix_entry)

    ok_count = sum(1 for p in proposed_fixes if p["diff"])
    err_count = len(proposed_fixes) - ok_count
    rule_count = sum(1 for p in proposed_fixes if p.get("method") == "RULE")
    llm_count = sum(1 for p in proposed_fixes if p.get("method") == "LLM")

    logger.info(f"=== FIX GENERATOR DONE: {ok_count} diffs ({llm_count} LLM, {rule_count} rule-based), {err_count} errors ===")
    for p in proposed_fixes:
        method = p.get("method", "NONE")
        status = f"OK ({method})" if p["diff"] else f"ERR: {p.get('generation_error','?')}"
        logger.info(f"  → {p['file']}: {status}")

    return {
        "proposed_fixes": proposed_fixes,
        "current_node": "fix_generator",
        "status_message": f"Generated {ok_count} patches ({llm_count} LLM, {rule_count} rule-based, {err_count} errors)",
    }


def _read_file_with_numbers(repo_path: str, relative_path: str) -> tuple[str, int]:
    """Read file and return (content with line numbers, total line count)."""
    if not repo_path or not relative_path:
        return "", 0
    full_path = os.path.join(repo_path, relative_path)
    try:
        with open(full_path) as f:
            lines = f.readlines()
        numbered = "".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))
        return numbered, len(lines)
    except OSError:
        return "", 0


def _find_matching_failure_dict(failures: list, file_rel: str, line: int) -> dict | None:
    """Find the most relevant failure dict for this classification."""
    # Try exact match on source_file
    for f in failures:
        if f.get("source_file", "") == file_rel:
            return f
    # Try partial match
    for f in failures:
        sf = f.get("source_file", "")
        if sf and (sf in file_rel or file_rel in sf):
            return f
    # Fall back to first failure
    if failures:
        return failures[0]
    return None


def _format_failure(f: dict) -> str:
    parts = []
    if f.get("test_name"):
        parts.append(f"Test: {f['test_name']}")
    if f.get("error_message"):
        parts.append(f"Error: {f['error_message']}")
    if f.get("traceback"):
        parts.append(f"Traceback:\n{f['traceback'][:1500]}")
    return "\n".join(parts)


def _extract_diff(raw: str) -> str:
    """Extract the unified diff from Claude's response, stripping markdown fences."""
    text = raw.strip()
    # Strip markdown code fences
    if "```" in text:
        lines = text.split("\n")
        in_fence = False
        diff_lines = []
        for line in lines:
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or line.startswith("---") or line.startswith("+++") or \
               line.startswith("@@") or line.startswith("+") or \
               line.startswith("-") or line.startswith(" "):
                diff_lines.append(line)
        if diff_lines:
            return "\n".join(diff_lines)
    # If no fences, try to find diff starting from "--- "
    idx = text.find("--- ")
    if idx >= 0:
        return text[idx:]
    return text


def _validate_diff(diff: str, file_rel: str, file_lines: int) -> str | None:
    """
    Validate a unified diff. Returns error string or None if valid.
    """
    if not diff or not diff.strip():
        return "Empty diff"

    lines = diff.strip().split("\n")

    # Must start with "--- "
    if not lines[0].startswith("--- "):
        return "Diff does not start with '--- '"

    # Must contain "+++ "
    has_plus = any(l.startswith("+++ ") for l in lines)
    if not has_plus:
        return "Diff missing '+++ ' header"

    # Count changed lines (lines starting with + or - but not headers)
    changed = 0
    for l in lines:
        if (l.startswith("+") and not l.startswith("+++ ")) or \
           (l.startswith("-") and not l.startswith("--- ")):
            changed += 1

    # Reject full-file rewrites: >200 changed lines unless file is tiny
    if changed > 200 and file_lines > 250:
        return f"Diff too large: {changed} changed lines (likely full rewrite)"

    return None
