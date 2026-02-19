import os
import subprocess

from app.models.state import HealingState
from app.services.sandbox import run_command, run_tests
from app.utils.framework_detector import get_test_command
from app.utils.logger import get_logger

logger = get_logger("fix_validator")

# Filename for temp diff inside repo (visible to Docker mount)
_PATCH_FILENAME = ".ci_heal_patch.diff"


async def fix_validator_node(state: HealingState) -> dict:
    """
    For each proposed fix: apply patch, run tests, revert if worse.
    Produces fixes_applied list with status="fixed" or "failed".
    Does NOT commit or push.
    """
    proposed = state.get("proposed_fixes", [])
    repo_path = state.get("repo_path", "")
    iteration = state.get("iteration", 0)
    test_framework = state.get("test_framework", "pytest")
    package_manager = state.get("package_manager", "pip")
    test_files = state.get("test_files", [])

    logger.info(f"=== FIX VALIDATOR: iteration={iteration}, proposed={len(proposed)} fixes ===")

    if not proposed:
        logger.info("No proposed fixes to validate")
        return {
            "fixes_applied": [],
            "current_node": "fix_validator",
            "status_message": "No fixes to validate",
        }

    # Compute commit message for this iteration (git_ops will actually commit)
    bug_types = sorted(set(p.get("bug_type", "LOGIC") for p in proposed if p.get("diff")))
    types_str = ", ".join(bug_types) if bug_types else "LOGIC"
    commit_msg = f"[AI-AGENT] Iteration {iteration}: Fix {types_str} issues"

    # If repo_path is invalid, mark everything failed
    if not repo_path or not os.path.isdir(repo_path):
        logger.error(f"repo_path invalid: {repo_path}")
        return {
            "fixes_applied": [
                _make_applied_fix(p, "failed", commit_msg, iteration)
                for p in proposed
            ],
            "current_node": "fix_validator",
            "status_message": "repo_path invalid — all fixes failed",
        }

    test_cmd = get_test_command(test_framework, package_manager, test_files)
    fixes_applied = []

    for idx, fix in enumerate(proposed):
        diff = fix.get("diff", "")
        file_rel = fix.get("file", "")

        logger.info(f"  [{idx+1}/{len(proposed)}] Validating fix for {file_rel} ({fix.get('bug_type', '?')})")

        # A) Skip if no diff or generation_error
        if not diff or fix.get("generation_error"):
            reason = fix.get("generation_error", "no diff")
            logger.info(f"    SKIP: {reason}")
            fixes_applied.append(
                _make_applied_fix(fix, "failed", commit_msg, iteration)
            )
            continue

        # Save original content for fallback revert
        full_path = os.path.join(repo_path, file_rel)
        original_content = _read_file_safe(full_path)

        try:
            status = await _try_apply_and_test(
                repo_path, file_rel, full_path, diff, test_cmd, original_content,
            )
        except Exception as e:
            logger.error(f"    Unexpected error validating {file_rel}: {e}")
            _revert_file(repo_path, file_rel, full_path, original_content)
            status = "failed"

        applied = _make_applied_fix(fix, status, commit_msg, iteration)
        fixes_applied.append(applied)
        logger.info(f"    RESULT: {file_rel} → {status}")

    fixed_count = sum(1 for f in fixes_applied if f["status"] == "fixed")
    failed_count = len(fixes_applied) - fixed_count

    logger.info(f"=== FIX VALIDATOR DONE: {fixed_count} fixed, {failed_count} failed ===")

    return {
        "fixes_applied": fixes_applied,
        "current_node": "fix_validator",
        "status_message": f"Validated {len(fixes_applied)} fixes: {fixed_count} fixed, {failed_count} failed",
    }


async def _try_apply_and_test(
    repo_path: str,
    file_rel: str,
    full_path: str,
    diff: str,
    test_cmd: str,
    original_content: str | None,
) -> str:
    """Apply patch, test, revert if bad. Returns 'fixed' or 'failed'."""

    # Write diff file INSIDE repo_path so Docker mount can see it
    patch_path = os.path.join(repo_path, _PATCH_FILENAME)
    try:
        with open(patch_path, "w") as f:
            f.write(diff)
    except OSError as e:
        logger.error(f"    Cannot write patch file: {e}")
        return "failed"

    try:
        # B1) Dry-run — use relative path so it works in both Docker and subprocess
        dry = run_command(
            repo_path,
            f"patch -p1 --dry-run < {_PATCH_FILENAME}",
            timeout=30,
        )
        if dry.returncode != 0:
            logger.warning(f"    Dry-run failed: {dry.stderr[:300]}")
            logger.warning(f"    Dry-run stdout: {dry.stdout[:300]}")
            return "failed"

        logger.info(f"    Dry-run OK, applying patch...")

        # B2) Apply for real
        apply = run_command(
            repo_path,
            f"patch -p1 < {_PATCH_FILENAME}",
            timeout=30,
        )
        if apply.returncode != 0:
            logger.warning(f"    Patch apply failed: {apply.stderr[:300]}")
            _revert_file(repo_path, file_rel, full_path, original_content)
            return "failed"

        logger.info(f"    Patch applied, running tests...")

        # B3) Run tests
        try:
            result = run_tests(repo_path, test_cmd)
        except Exception as e:
            logger.warning(f"    Test execution failed after patching {file_rel}: {e}")
            _revert_file(repo_path, file_rel, full_path, original_content)
            return "failed"

        # B4) Decide
        if result.returncode == 0:
            logger.info(f"    Tests PASS after patch — keeping fix")
            return "fixed"
        else:
            logger.info(f"    Tests still FAIL after patch (rc={result.returncode}), reverting")
            logger.debug(f"    Test stdout: {result.stdout[:500]}")
            _revert_file(repo_path, file_rel, full_path, original_content)
            return "failed"

    finally:
        # Clean up patch file from repo
        try:
            os.unlink(patch_path)
        except OSError:
            pass


def _revert_file(
    repo_path: str,
    file_rel: str,
    full_path: str,
    original_content: str | None,
) -> None:
    """Revert a file: try git checkout first, fallback to restoring saved content."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "checkout", "--", file_rel],
            capture_output=True,
            timeout=10,
        )
        if r.returncode == 0:
            logger.info(f"    Reverted {file_rel} via git checkout")
            return
    except Exception:
        pass

    # Fallback: write original content
    if original_content is not None:
        try:
            with open(full_path, "w") as f:
                f.write(original_content)
            logger.info(f"    Reverted {file_rel} from saved content")
        except OSError as e:
            logger.error(f"    Failed to restore {full_path}: {e}")


def _read_file_safe(path: str) -> str | None:
    """Read file contents, return None on failure."""
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


def _make_applied_fix(fix: dict, status: str, commit_msg: str, iteration: int) -> dict:
    """Build an AppliedFix dict from a proposed fix."""
    return {
        "file": fix.get("file", ""),
        "bug_type": fix.get("bug_type", "LOGIC"),
        "line_number": fix.get("line_number", 0),
        "issue_line": fix.get("issue_line", ""),
        "commit_message": commit_msg,
        "status": status,
        "diff": fix.get("diff", ""),
        "iteration": iteration,
    }
