"""
E2E simulation: walks through the entire pipeline node-by-node
with a real (local) broken repo. Mocks only external services
(Claude API, GitHub Actions, git push).

This test verifies the full autonomous loop:
  repo_analyzer → test_runner → bug_classifier → fix_generator →
  fix_validator → git_ops → ci_monitor → scorer

Run with: python -m pytest tests/test_e2e_simulation.py -v -s
"""
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from unittest.mock import patch, AsyncMock, MagicMock

import pytest


# ── Helper: create a broken Python repo ──────────────────────────

def _create_broken_repo(base_dir: str) -> str:
    """
    Create a minimal Python repo with:
    - src/utils.py that has a LOGIC bug (add returns a - b instead of a + b)
    - tests/test_utils.py that asserts add(2,3) == 5
    """
    repo_dir = os.path.join(base_dir, "repo")
    os.makedirs(os.path.join(repo_dir, "src"))
    os.makedirs(os.path.join(repo_dir, "tests"))

    # Broken source file
    with open(os.path.join(repo_dir, "src", "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(repo_dir, "src", "utils.py"), "w") as f:
        f.write(
            "def add(a, b):\n"
            "    return a - b  # BUG: should be a + b\n"
        )

    # Test file
    with open(os.path.join(repo_dir, "tests", "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(repo_dir, "tests", "test_utils.py"), "w") as f:
        f.write(
            "from src.utils import add\n\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        )

    # Initialize as git repo
    subprocess.run(["git", "init", repo_dir], capture_output=True, check=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.name", "Test"], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "config", "user.email", "test@test.com"], capture_output=True)
    subprocess.run(["git", "-C", repo_dir, "add", "."], capture_output=True, check=True)
    subprocess.run(["git", "-C", repo_dir, "commit", "-m", "init"], capture_output=True, check=True)

    return repo_dir


# ── The E2E test ──────────────────────────────────────────────────

class TestE2ESimulation:
    """Walk through the pipeline node by node with a real broken repo."""

    def _run(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_full_pipeline_simulation(self):
        """
        Simulate the complete healing flow:
        1. repo_analyzer (mocked clone, real detection)
        2. test_runner (real pytest execution)
        3. bug_classifier (mocked Claude for LOGIC)
        4. fix_generator (mocked Claude returns valid diff)
        5. fix_validator (real patch + real test)
        6. git_ops (real commit, mocked push)
        7. ci_monitor (mocked - LOCAL_ONLY)
        8. scorer (real)
        """
        tmpdir = tempfile.mkdtemp(prefix="e2e_heal_")

        try:
            # Create the broken repo
            repo_dir = _create_broken_repo(tmpdir)
            print(f"\n{'='*60}")
            print(f"E2E SIMULATION — Broken repo at: {repo_dir}")
            print(f"{'='*60}")

            # Create feature branch
            subprocess.run(
                ["git", "-C", repo_dir, "checkout", "-b", "TEST_TEAM_TEST_LEADER_AI_Fix"],
                capture_output=True, check=True,
            )

            # ── State (simulates what orchestrator sets up) ──
            state = {
                "repo_url": "https://github.com/test/repo",
                "team_name": "TEST TEAM",
                "leader_name": "Test Leader",
                "github_token": "fake_token",
                "run_id": "e2e-test-run",
                "repo_path": repo_dir,
                "branch_name": "TEST_TEAM_TEST_LEADER_AI_Fix",
                "language": "python",
                "test_framework": "pytest",
                "package_manager": "pip",
                "test_files": ["tests/test_utils.py"],
                "project_structure": {},
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "failures": [],
                "all_tests_passing": False,
                "classifications": [],
                "proposed_fixes": [],
                "fixes_applied": [],
                "last_commit_sha": "",
                "total_commits": 0,
                "ci_runs": [],
                "ci_passed": False,
                "iteration": 0,
                "max_iterations": 5,
                "start_time": "2026-01-01T00:00:00+00:00",
                "end_time": None,
                "duration_seconds": 0.0,
                "score": {},
                "current_node": "",
                "status_message": "",
                "error": None,
            }

            # ──────────────────────────────────────────────────
            # STEP 1: test_runner (iteration 1)
            # ──────────────────────────────────────────────────
            print("\n--- STEP 1: test_runner (iteration 1) ---")
            from app.agents.nodes.test_runner import test_runner_node as _test_runner

            result = self._run(_test_runner(state))
            state.update(result)

            print(f"  Total tests: {state['total_tests']}")
            print(f"  Passed: {state['passed_tests']}")
            print(f"  Failed: {state['failed_tests']}")
            print(f"  All passing: {state['all_tests_passing']}")
            for f in state["failures"]:
                print(f"  Failure: {f['test_name']} — {f['error_message'][:80]}")

            assert state["failed_tests"] > 0, "Should detect failures"
            assert not state["all_tests_passing"], "Tests should not all pass"
            assert state["iteration"] == 1

            # ──────────────────────────────────────────────────
            # STEP 2: bug_classifier
            # ──────────────────────────────────────────────────
            print("\n--- STEP 2: bug_classifier ---")

            # The failure is an AssertionError — rules won't match, so LLM fires.
            # Mock the Claude LLM response.
            llm_classify_response = json.dumps({
                "bug_type": "LOGIC",
                "confidence": 0.9,
                "root_cause": "add function subtracts instead of adding",
                "affected_file": "src/utils.py",
                "affected_line": 2,
                "fix_summary": "change - to + in return statement",
            })

            from app.agents.nodes.bug_classifier import bug_classifier_node

            with patch("app.agents.nodes.bug_classifier.openai_service") as mock_cs:
                mock_cs.get_client.return_value = MagicMock()
                mock_cs.classify_bug = AsyncMock(return_value=llm_classify_response)

                result = self._run(bug_classifier_node(state))
                state.update(result)

            print(f"  Classifications: {len(state['classifications'])}")
            for c in state["classifications"]:
                print(f"    {c['bug_type']} in {c['file']} line {c['line']} "
                      f"(method={c['method']}, confidence={c['confidence']})")

            assert len(state["classifications"]) > 0, "Should have classifications"

            # ──────────────────────────────────────────────────
            # STEP 3: fix_generator
            # ──────────────────────────────────────────────────
            print("\n--- STEP 3: fix_generator ---")

            # Mock Claude to return a valid unified diff
            fix_diff = (
                "--- a/src/utils.py\n"
                "+++ b/src/utils.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b  # BUG: should be a + b\n"
                "+    return a + b\n"
            )

            from app.agents.nodes.fix_generator import fix_generator_node

            with patch("app.agents.nodes.fix_generator.openai_service") as mock_cs:
                mock_cs.get_client.return_value = MagicMock()
                mock_cs.generate_fix = AsyncMock(return_value=fix_diff)

                result = self._run(fix_generator_node(state))
                state.update(result)

            print(f"  Proposed fixes: {len(state['proposed_fixes'])}")
            for p in state["proposed_fixes"]:
                has_diff = "YES" if p.get("diff") else "NO"
                print(f"    {p['file']}: diff={has_diff}, error={p.get('generation_error', 'none')}")

            assert len(state["proposed_fixes"]) > 0, "Should have proposed fixes"
            assert state["proposed_fixes"][0]["diff"], "First fix should have a diff"

            # ──────────────────────────────────────────────────
            # STEP 4: fix_validator (REAL patch + REAL test)
            # ──────────────────────────────────────────────────
            print("\n--- STEP 4: fix_validator (real patch + real test) ---")

            from app.agents.nodes.fix_validator import fix_validator_node

            result = self._run(fix_validator_node(state))

            # Merge fixes_applied (Annotated list uses operator.add)
            new_fixes = result.get("fixes_applied", [])
            state["fixes_applied"] = state["fixes_applied"] + new_fixes
            state["current_node"] = result.get("current_node", "")
            state["status_message"] = result.get("status_message", "")

            print(f"  Fixes applied: {len(new_fixes)}")
            for f in new_fixes:
                print(f"    {f['file']}: status={f['status']}, bug_type={f['bug_type']}")

            fixed_count = sum(1 for f in new_fixes if f["status"] == "fixed")
            print(f"  Fixed: {fixed_count}, Failed: {len(new_fixes) - fixed_count}")

            assert fixed_count > 0, "At least one fix should succeed"

            # Verify the source file was actually changed
            with open(os.path.join(repo_dir, "src", "utils.py")) as f:
                content = f.read()
            print(f"  File content after fix:\n    {content.strip()}")
            assert "a + b" in content, "Fix should have changed - to +"

            # ──────────────────────────────────────────────────
            # STEP 5: git_ops (real commit, mocked push)
            # ──────────────────────────────────────────────────
            print("\n--- STEP 5: git_ops (real commit, mocked push) ---")

            from app.agents.nodes.git_ops import git_ops_node

            with patch("app.services.github_service.subprocess") as mock_sub:
                # Make subprocess calls work normally EXCEPT git push
                import subprocess as real_subprocess

                def selective_run(*args, **kwargs):
                    cmd = args[0] if args else kwargs.get("args", [])
                    if isinstance(cmd, list) and "push" in cmd:
                        # Mock the push
                        return MagicMock(returncode=0)
                    return real_subprocess.run(*args, **kwargs)

                def selective_check_output(*args, **kwargs):
                    return real_subprocess.check_output(*args, **kwargs)

                mock_sub.run = selective_run
                mock_sub.check_output = selective_check_output

                result = self._run(git_ops_node(state))
                state.update(result)

            sha = state.get("last_commit_sha", "")
            print(f"  Commit SHA: {sha[:12] if sha else 'NONE'}")
            print(f"  Total commits: {state.get('total_commits', 0)}")

            assert sha, "Should have a commit SHA"
            assert state["total_commits"] == 1

            # Verify commit message
            log = subprocess.check_output(
                ["git", "-C", repo_dir, "log", "--oneline", "-1"]
            ).decode().strip()
            print(f"  Git log: {log}")
            assert "[AI-AGENT]" in log, "Commit should have [AI-AGENT] prefix"

            # ──────────────────────────────────────────────────
            # STEP 6: ci_monitor (LOCAL_ONLY — no real GitHub)
            # ──────────────────────────────────────────────────
            print("\n--- STEP 6: ci_monitor ---")

            # Re-run tests to check if they pass now
            from app.agents.nodes.test_runner import test_runner_node as _test_runner2
            retest = self._run(_test_runner2(state))

            # If tests pass, set all_tests_passing before ci_monitor
            state["all_tests_passing"] = retest.get("all_tests_passing", False)
            print(f"  Tests after fix: all_passing={state['all_tests_passing']}")

            from app.agents.nodes.ci_monitor import ci_monitor_node

            # Force LOCAL_ONLY by clearing the SHA (no real GitHub to poll)
            saved_sha = state["last_commit_sha"]
            state["last_commit_sha"] = ""  # force LOCAL_ONLY

            result = self._run(ci_monitor_node(state))
            ci_runs = result.get("ci_runs", [])
            state["ci_runs"] = state["ci_runs"] + ci_runs
            state["ci_passed"] = result.get("ci_passed", False)

            print(f"  CI passed: {state['ci_passed']}")
            for cr in ci_runs:
                print(f"    Iteration {cr['iteration']}: {cr['status']} ({cr['mode']})")

            state["last_commit_sha"] = saved_sha  # restore

            # ──────────────────────────────────────────────────
            # STEP 7: scorer
            # ──────────────────────────────────────────────────
            print("\n--- STEP 7: scorer ---")

            from app.agents.nodes.scorer import scorer_node

            result = self._run(scorer_node(state))
            state.update(result)

            print(f"  Score: {state['score']}")
            print(f"  Duration: {state['duration_seconds']:.1f}s")

            assert state["score"]["total"] > 0, "Score should be positive"

            # ──────────────────────────────────────────────────
            # FINAL SUMMARY
            # ──────────────────────────────────────────────────
            print(f"\n{'='*60}")
            print("E2E SIMULATION COMPLETE")
            print(f"{'='*60}")
            print(f"  Iterations: {state['iteration']}")
            print(f"  Failures detected: {state['failed_tests']}")
            print(f"  Fixes applied: {sum(1 for f in state['fixes_applied'] if f['status'] == 'fixed')}")
            print(f"  Commits: {state['total_commits']}")
            print(f"  CI passed: {state['ci_passed']}")
            print(f"  Final score: {state['score']['total']}")
            print(f"  Tests all passing: {state['all_tests_passing']}")
            print(f"{'='*60}\n")

            assert state["all_tests_passing"], "Tests should be passing after fix"

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
