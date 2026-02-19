from app.models.state import HealingState
from app.services.github_service import safe_commit_and_push, redact_secrets
from app.utils.logger import get_logger

logger = get_logger("git_ops")


async def git_ops_node(state: HealingState) -> dict:
    """
    Commit all successful fixes from this iteration and push.
    ONE commit per iteration. Skips if no files were fixed.
    Always explicitly sets last_commit_sha so ci_monitor knows whether to poll.
    """
    iteration = state.get("iteration", 0)
    repo_path = state.get("repo_path", "")
    branch_name = state.get("branch_name", "")
    fixes_applied = state.get("fixes_applied", [])

    # Collect files that were fixed in THIS iteration
    fixed_files = []
    bug_types = []
    for fix in fixes_applied:
        if fix.get("iteration") == iteration and fix.get("status") == "fixed":
            fixed_files.append(fix["file"])
            bug_types.append(fix["bug_type"])

    all_this_iter = [f for f in fixes_applied if f.get("iteration") == iteration]
    logger.info(f"=== GIT OPS: iteration={iteration}, branch={branch_name} ===")
    logger.info(f"  Total fixes_applied so far: {len(fixes_applied)}")
    logger.info(f"  This iteration: {len(all_this_iter)} total, {len(fixed_files)} fixed")
    for f in all_this_iter:
        logger.info(f"    {f['file']}: status={f['status']}, bug_type={f['bug_type']}")

    if not fixed_files:
        logger.info(f"Iteration {iteration}: No files fixed, skipping commit")
        return {
            "last_commit_sha": "",
            "current_node": "git_ops",
            "status_message": f"Iteration {iteration}: No changes to commit",
        }

    try:
        sha = safe_commit_and_push(
            repo_path=repo_path,
            branch_name=branch_name,
            iteration=iteration,
            bug_types=bug_types,
            fixed_files=fixed_files,
        )
    except (RuntimeError, Exception) as e:
        safe_error = redact_secrets(str(e))
        logger.error(f"Git error: {safe_error}")
        return {
            "last_commit_sha": "",
            "current_node": "git_ops",
            "status_message": f"Git error: {safe_error}",
            "error": safe_error,
        }

    if sha is None:
        logger.info(f"Iteration {iteration}: No staged changes after add")
        return {
            "last_commit_sha": "",
            "current_node": "git_ops",
            "status_message": f"Iteration {iteration}: No staged changes",
        }

    total_commits = state.get("total_commits", 0) + 1

    logger.info(f"Iteration {iteration}: Committed {sha[:8]}, {len(fixed_files)} files, total commits: {total_commits}")

    return {
        "last_commit_sha": sha,
        "total_commits": total_commits,
        "current_node": "git_ops",
        "status_message": f"Committed {sha[:8]} ({len(fixed_files)} files)",
    }
