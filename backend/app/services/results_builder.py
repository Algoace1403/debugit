"""
Converts HealingState -> results.json schema.
NEVER includes github_token. Uses format_issue_line() for all issue_line fields.
"""
from app.services.scoring import calculate_score


def build_results(state: dict) -> dict:
    """Build results.json dict from current HealingState. Safe to persist."""
    fixes = []
    for fix in state.get("fixes_applied", []):
        fixes.append({
            "file": fix.get("file", ""),
            "bug_type": fix.get("bug_type", ""),
            "line_number": fix.get("line_number", 0),
            "issue_line": fix.get("issue_line", ""),
            "commit_message": fix.get("commit_message", ""),
            "status": fix.get("status", "failed"),
            "iteration": fix.get("iteration", 0),
            "diff": fix.get("diff", ""),
        })

    ci_runs = []
    for run in state.get("ci_runs", []):
        ci_runs.append({
            "iteration": run.get("iteration", 0),
            "status": run.get("status", "FAILED"),
            "mode": run.get("mode", "LOCAL_ONLY"),
            "run_url": run.get("run_url", ""),
            "timestamp": run.get("timestamp", ""),
            "failures_remaining": run.get("failures_remaining", 0),
        })

    duration = state.get("duration_seconds", 0.0)
    total_commits = state.get("total_commits", 0)
    score = state.get("score") or calculate_score(duration, total_commits)

    total_fixed = sum(1 for f in fixes if f["status"] == "fixed")
    all_passing = state.get("all_tests_passing", False) or state.get("ci_passed", False)

    return {
        "repo_url": state.get("repo_url", ""),
        "team_name": state.get("team_name", ""),
        "leader_name": state.get("leader_name", ""),
        "branch_name": state.get("branch_name", ""),
        "start_time": state.get("start_time", ""),
        "end_time": state.get("end_time"),
        "total_time_seconds": duration,
        "total_failures_detected": state.get("failed_tests", 0),
        "total_fixes_applied": total_fixed,
        "total_commits": total_commits,
        "final_status": "PASSED" if all_passing else "FAILED",
        "score": score,
        "fixes": fixes,
        "ci_runs": ci_runs,
        # NOTE: github_token is NEVER included
    }
