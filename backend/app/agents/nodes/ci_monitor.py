import asyncio
import os
from datetime import datetime, timezone

import httpx

from app.models.state import HealingState
from app.services.github_service import parse_github_url
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("ci_monitor")


async def ci_monitor_node(state: HealingState) -> dict:
    """
    Poll GitHub Actions for CI status on our branch + commit SHA.
    Falls back to LOCAL_ONLY if no workflow is detected within 60s.
    """
    iteration = state.get("iteration", 0)
    branch = state.get("branch_name", "")
    commit_sha = state.get("last_commit_sha", "")
    local_passing = state.get("all_tests_passing", False)
    now_str = datetime.now(timezone.utc).isoformat()

    logger.info(f"=== CI MONITOR: iteration={iteration}, branch={branch}, sha={commit_sha[:8] if commit_sha else 'NONE'} ===")

    # If no commit was made this iteration (git_ops returned None), use local results
    if not commit_sha:
        logger.info(f"Iteration {iteration}: No commit SHA, using local test results")
        ci_run = {
            "iteration": iteration,
            "status": "PASSED" if local_passing else "FAILED",
            "mode": "LOCAL_ONLY",
            "run_url": "",
            "timestamp": now_str,
            "failures_remaining": state.get("failed_tests", 0),
        }
        return {
            "ci_passed": local_passing,
            "ci_runs": [ci_run],
            "current_node": "ci_monitor",
            "status_message": f"No commit — local tests {'PASSED' if local_passing else 'FAILED'}",
        }

    # Try to poll GitHub Actions
    try:
        repo_url = state.get("repo_url", "")
        owner, repo = parse_github_url(repo_url)
        token = settings.github_token

        if not token:
            raise ValueError("No GITHUB_TOKEN configured")

        result = await _poll_github_actions(
            owner=owner,
            repo=repo,
            branch=branch,
            commit_sha=commit_sha,
            token=token,
            local_passing=local_passing,
        )
    except Exception as e:
        logger.warning(f"CI monitoring failed: {e}. Falling back to local results.")
        result = {
            "status": "PASSED" if local_passing else "FAILED",
            "mode": "LOCAL_ONLY",
            "run_url": "",
            "conclusion": None,
        }

    ci_passed = result["status"] == "PASSED"
    ci_run = {
        "iteration": iteration,
        "status": result["status"],
        "mode": result["mode"],
        "run_url": result.get("run_url", ""),
        "timestamp": now_str,
        "failures_remaining": 0 if ci_passed else state.get("failed_tests", 0),
    }

    logger.info(f"Iteration {iteration}: CI {result['status']} (mode={result['mode']})")

    return {
        "ci_passed": ci_passed,
        "ci_runs": [ci_run],
        "current_node": "ci_monitor",
        "status_message": f"CI {result['status']} ({result['mode']})",
    }


async def _poll_github_actions(
    owner: str,
    repo: str,
    branch: str,
    commit_sha: str,
    token: str,
    local_passing: bool,
    max_wait: int = 300,
) -> dict:
    """
    Poll GitHub Actions API for a workflow run matching branch + SHA.
    Returns dict with status, mode, run_url, conclusion.
    """
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    base_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"

    async with httpx.AsyncClient(timeout=30) as client:
        # Phase 1: Wait for workflow run to appear (max 60s)
        delay = 5
        elapsed = 0
        run_data = None

        while elapsed < 60:
            await asyncio.sleep(delay)
            elapsed += delay

            try:
                resp = await client.get(
                    base_url,
                    params={"branch": branch, "head_sha": commit_sha, "per_page": 5},
                    headers=headers,
                )
                if resp.status_code == 200:
                    runs = resp.json().get("workflow_runs", [])
                    if runs:
                        run_data = runs[0]
                        break
            except httpx.RequestError as e:
                logger.warning(f"GitHub API request failed: {e}")

            delay = min(delay * 1.5, 30)

        # No CI workflow found → LOCAL_ONLY
        if run_data is None:
            return {
                "status": "PASSED" if local_passing else "FAILED",
                "mode": "LOCAL_ONLY",
                "run_url": "",
                "conclusion": None,
            }

        # Phase 2: Poll until completion
        remaining = max_wait - elapsed
        delay = 15

        while remaining > 0:
            await asyncio.sleep(delay)
            remaining -= delay

            try:
                resp = await client.get(
                    f"{base_url}/{run_data['id']}",
                    headers=headers,
                )
                data = resp.json()
                if data.get("status") == "completed":
                    return {
                        "status": "PASSED" if data["conclusion"] == "success" else "FAILED",
                        "mode": "CI",
                        "run_url": data.get("html_url", ""),
                        "conclusion": data["conclusion"],
                    }
            except httpx.RequestError as e:
                logger.warning(f"GitHub API poll failed: {e}")

            delay = min(delay * 1.5, 60)

        # Timeout
        return {
            "status": "FAILED",
            "mode": "CI",
            "run_url": run_data.get("html_url", ""),
            "conclusion": "timed_out",
        }
