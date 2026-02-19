"""
Orchestrator: runs the LangGraph pipeline as a background task.
- Streams node events to WebSocket via HealingCallback.
- Persists state + results.json after each node.
- Redacts github_token from all persisted/broadcast data.
- ALWAYS generates results.json, even on fatal errors.
"""
import asyncio
from datetime import datetime, timezone

from app.agents.graph import build_graph
from app.agents.callbacks import HealingCallback
from app.services.run_store import run_store
from app.services.results_builder import build_results
from app.services.github_service import redact_state, redact_secrets
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("orchestrator")

# Human-readable node descriptions for WebSocket messages
_NODE_DESCRIPTIONS = {
    "repo_analyzer": "Cloning repository and detecting project structure",
    "test_runner": "Running test suite",
    "bug_classifier": "Analyzing and classifying failures",
    "fix_generator": "Generating code fixes with AI",
    "fix_validator": "Applying and validating patches",
    "git_ops": "Committing fixes and pushing to branch",
    "ci_monitor": "Monitoring CI/CD pipeline status",
    "scorer": "Calculating final score",
}


async def run_healing_pipeline(
    run_id: str,
    repo_url: str,
    team_name: str,
    leader_name: str,
) -> None:
    """
    Execute the full LangGraph healing pipeline.
    Called as a background task from POST /api/v1/heal.
    """
    callback = HealingCallback(run_id)
    start_time = datetime.now(timezone.utc).isoformat()

    # Build initial state — github_token from ENV only
    initial_state = {
        "repo_url": repo_url,
        "team_name": team_name,
        "leader_name": leader_name,
        "github_token": settings.github_token,  # FROM ENV, never from request
        "run_id": run_id,
        # Repo analysis (filled by repo_analyzer)
        "repo_path": "",
        "branch_name": "",
        "language": "",
        "test_framework": "",
        "package_manager": "",
        "test_files": [],
        "project_structure": {},
        # Test results
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "failures": [],
        "all_tests_passing": False,
        # Classifications
        "classifications": [],
        # Proposed fixes (current iteration, from fix_generator → fix_validator)
        "proposed_fixes": [],
        # Fixes (Annotated list — accumulates via operator.add)
        "fixes_applied": [],
        # Git
        "last_commit_sha": "",
        "total_commits": 0,
        # CI (Annotated list — accumulates via operator.add)
        "ci_runs": [],
        "ci_passed": False,
        # Loop control
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        # Scoring
        "start_time": start_time,
        "end_time": None,
        "duration_seconds": 0.0,
        "score": {},
        # Progress
        "current_node": "",
        "status_message": "Initializing...",
        "error": None,
    }

    # Persist initial state (redacted — no token on disk)
    await run_store.create(run_id, redact_state(initial_state))
    # Save initial results.json skeleton
    await run_store.save_results(run_id, build_results(initial_state))

    try:
        graph = build_graph()
        await callback.on_progress("Pipeline started — analyzing repository", {"run_id": run_id})

        # Stream through graph — LangGraph yields partial state updates after each node
        last_state = initial_state
        async for event in graph.astream(initial_state, stream_mode="updates"):
            # event is a dict like {"node_name": {partial_state_update}}
            for node_name, node_output in event.items():
                if node_name == "__start__":
                    continue

                # Human-readable WS message
                description = _NODE_DESCRIPTIONS.get(node_name, f"Running {node_name}")
                iteration = last_state.get("iteration", 0)
                if node_name == "test_runner":
                    description = f"Running test suite (iteration {iteration + 1})"
                elif node_name == "git_ops" and iteration > 0:
                    description = f"Committing fixes (iteration {iteration})"

                await callback.on_node_start(node_name, description)

                # Merge node output into our tracking copy
                for k, v in node_output.items():
                    if isinstance(v, list) and isinstance(last_state.get(k), list):
                        # Respect Annotated[list, operator.add] semantics
                        last_state[k] = last_state[k] + v
                    else:
                        last_state[k] = v

                # Persist after each node (redacted)
                await run_store.update_state(run_id, redact_state(node_output))
                await run_store.save_results(run_id, build_results(last_state))

                # Build descriptive end message
                status_msg = _build_node_end_message(node_name, node_output, last_state)

                await callback.on_node_end(
                    node_name,
                    status_msg,
                    data=_safe_summary(last_state),
                )

        # Pipeline complete
        final_results = build_results(last_state)
        await run_store.save_results(run_id, final_results)
        await run_store.update_state(run_id, {"status": "completed"})

        score_total = final_results['score'].get('total', 0)
        final_status = final_results.get('final_status', 'UNKNOWN')
        await callback.on_complete(
            f"Healing complete — {final_status}. Score: {score_total}",
            data=final_results,
        )
        logger.info(f"Run {run_id} completed. Status={final_status}, Score={score_total}")

    except Exception as e:
        # Redact secrets from error message
        safe_error = redact_secrets(str(e))
        logger.error(f"Run {run_id} failed: {safe_error}")

        # FAIL-SAFE: Always generate results.json even on fatal error
        last_state["error"] = safe_error
        last_state["end_time"] = datetime.now(timezone.utc).isoformat()
        if last_state.get("start_time"):
            try:
                start = datetime.fromisoformat(last_state["start_time"])
                last_state["duration_seconds"] = (
                    datetime.now(timezone.utc) - start
                ).total_seconds()
            except (ValueError, TypeError):
                pass

        final_results = build_results(last_state)
        try:
            await run_store.save_results(run_id, final_results)
        except Exception:
            pass  # best effort

        await run_store.update_state(run_id, {
            "error": safe_error,
            "status": "failed",
        })
        await callback.on_error(f"Pipeline failed: {safe_error}")


def _build_node_end_message(node_name: str, output: dict, state: dict) -> str:
    """Build a human-readable end message for each node."""
    if node_name == "repo_analyzer":
        lang = state.get("language", "unknown")
        fw = state.get("test_framework", "unknown")
        branch = state.get("branch_name", "")
        n_files = len(state.get("test_files", []))
        return f"Repository analyzed — {lang}/{fw}, {n_files} test files, branch: {branch}"

    if node_name == "test_runner":
        p = state.get("passed_tests", 0)
        t = state.get("total_tests", 0)
        f = state.get("failed_tests", 0)
        it = state.get("iteration", 0)
        if f == 0 and t > 0:
            return f"All {t} tests passing (iteration {it})"
        return f"{p}/{t} tests passing, {f} failing (iteration {it})"

    if node_name == "bug_classifier":
        n = len(state.get("classifications", []))
        return f"Classified {n} bug{'s' if n != 1 else ''}"

    if node_name == "fix_generator":
        proposed = state.get("proposed_fixes", [])
        ok = sum(1 for p in proposed if p.get("diff"))
        return f"Generated {ok} fix patch{'es' if ok != 1 else ''}"

    if node_name == "fix_validator":
        fixes = output.get("fixes_applied", [])
        fixed = sum(1 for f in fixes if f.get("status") == "fixed")
        failed = len(fixes) - fixed
        return f"{fixed} fix{'es' if fixed != 1 else ''} validated, {failed} failed"

    if node_name == "git_ops":
        sha = state.get("last_commit_sha", "")
        commits = state.get("total_commits", 0)
        if sha:
            return f"Committed {sha[:8]} (total: {commits} commit{'s' if commits != 1 else ''})"
        return "No changes to commit"

    if node_name == "ci_monitor":
        ci_runs = state.get("ci_runs", [])
        if ci_runs:
            last = ci_runs[-1]
            mode = last.get("mode", "")
            status = last.get("status", "")
            return f"CI status: {status} ({mode})"
        return "CI monitoring complete"

    if node_name == "scorer":
        score = state.get("score", {})
        return f"Final score: {score.get('total', 0)}"

    return output.get("status_message", f"{node_name} complete")


def _safe_summary(state: dict) -> dict:
    """Small summary dict safe for WS broadcast (no token, no huge fields)."""
    return {
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 5),
        "total_tests": state.get("total_tests", 0),
        "passed_tests": state.get("passed_tests", 0),
        "failed_tests": state.get("failed_tests", 0),
        "all_tests_passing": state.get("all_tests_passing", False),
        "total_commits": state.get("total_commits", 0),
        "branch_name": state.get("branch_name", ""),
        "current_node": state.get("current_node", ""),
        "last_commit_sha": state.get("last_commit_sha", ""),
    }
