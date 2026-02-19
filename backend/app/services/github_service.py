import subprocess
import os
import re
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("github_service")

# Timeout for all git subprocess calls (seconds)
_GIT_TIMEOUT = 120
_GIT_CONFIG_TIMEOUT = 10


def get_token() -> str:
    """Read GitHub token from environment ONLY."""
    return settings.github_token


def redact_secrets(text: str) -> str:
    """Strip any token/key patterns from a string before logging or returning as error."""
    safe = text
    # Redact GitHub tokens (ghp_, github_pat_, gho_, ghs_, ghr_)
    safe = re.sub(r'(ghp_|github_pat_|gho_|ghs_|ghr_)\S+', '***REDACTED***', safe)
    # Redact x-access-token:TOKEN@
    safe = re.sub(r'x-access-token:[^@]+@', 'x-access-token:***@', safe)
    # Redact OpenAI keys (sk-... pattern)
    safe = re.sub(r'sk-[A-Za-z0-9_\-]{20,}', '***REDACTED***', safe)
    # Redact any token from settings if it appears raw
    token = settings.github_token
    if token and len(token) > 8 and token in safe:
        safe = safe.replace(token, '***REDACTED***')
    api_key = settings.openai_api_key
    if api_key and len(api_key) > 8 and api_key in safe:
        safe = safe.replace(api_key, '***REDACTED***')
    return safe


def clone_repo(repo_url: str, dest_path: str) -> None:
    """Clone repo using token from env. Shallow clone for speed."""
    token = get_token()
    clone_url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, dest_path],
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        # Redact token from error before raising
        safe_msg = redact_secrets(str(e))
        safe_stderr = redact_secrets(e.stderr or "")
        raise RuntimeError(f"git clone failed: {safe_msg} {safe_stderr}") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("git clone timed out (120s)") from None

    # Configure git identity
    subprocess.run(
        ["git", "-C", dest_path, "config", "user.name", "CI-Heal-Agent"],
        capture_output=True, timeout=_GIT_CONFIG_TIMEOUT,
    )
    subprocess.run(
        ["git", "-C", dest_path, "config", "user.email", "agent@cihealer.dev"],
        capture_output=True, timeout=_GIT_CONFIG_TIMEOUT,
    )


def make_branch_name(team_name: str, leader_name: str) -> str:
    """
    Produce EXACT format: TEAM_NAME_LEADER_NAME_AI_Fix
    Prefix is uppercased. Suffix _AI_Fix is literal.
    """
    prefix = f"{team_name} {leader_name}".upper()
    prefix = prefix.replace(" ", "_").replace("-", "_")
    prefix = re.sub(r'[^A-Z0-9_]', '', prefix)
    prefix = re.sub(r'_+', '_', prefix)
    prefix = prefix.strip('_')
    return f"{prefix}_AI_Fix"


def create_branch(repo_path: str, branch_name: str) -> None:
    subprocess.run(
        ["git", "-C", repo_path, "checkout", "-b", branch_name],
        check=True,
        capture_output=True,
        text=True,
        timeout=_GIT_CONFIG_TIMEOUT,
    )


def safe_commit_and_push(
    repo_path: str,
    branch_name: str,
    iteration: int,
    bug_types: list[str],
    fixed_files: list[str],
) -> str | None:
    """
    Commit and push. Returns SHA or None if nothing to commit.
    Includes safety guardrails to prevent pushing to main.
    """
    # GUARDRAIL 1: Skip if no files to commit (cheap check first)
    if not fixed_files:
        return None

    # GUARDRAIL 2: Branch must end with _AI_Fix
    if not branch_name.endswith("_AI_Fix"):
        raise RuntimeError(f"ABORT: Branch '{branch_name}' missing _AI_Fix suffix")

    # GUARDRAIL 3: Never push to main/master (checked before git call too)
    if branch_name in ("main", "master"):
        raise RuntimeError("ABORT: Refusing to push to main/master")

    # GUARDRAIL 4: Verify correct branch via git
    current = subprocess.check_output(
        ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
        timeout=_GIT_CONFIG_TIMEOUT,
    ).decode().strip()
    if current != branch_name:
        raise RuntimeError(f"ABORT: On branch '{current}', expected '{branch_name}'")
    if current in ("main", "master"):
        raise RuntimeError("ABORT: Refusing to push to main/master")

    # Stage fixed files
    for f in fixed_files:
        subprocess.run(
            ["git", "-C", repo_path, "add", f],
            check=True, timeout=_GIT_CONFIG_TIMEOUT,
        )

    # Check if there are actual staged changes
    diff_result = subprocess.run(
        ["git", "-C", repo_path, "diff", "--cached", "--quiet"],
        capture_output=True, timeout=_GIT_CONFIG_TIMEOUT,
    )
    if diff_result.returncode == 0:
        return None  # nothing staged

    # Commit
    types_str = ", ".join(sorted(set(bug_types)))
    msg = f"[AI-AGENT] Iteration {iteration}: Fix {types_str} issues"
    subprocess.run(
        ["git", "-C", repo_path, "commit", "-m", msg],
        check=True, timeout=_GIT_CONFIG_TIMEOUT,
    )

    sha = subprocess.check_output(
        ["git", "-C", repo_path, "rev-parse", "HEAD"],
        timeout=_GIT_CONFIG_TIMEOUT,
    ).decode().strip()

    # Push to feature branch only
    try:
        subprocess.run(
            ["git", "-C", repo_path, "push", "-u", "origin", branch_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except subprocess.CalledProcessError as e:
        safe_msg = redact_secrets(str(e))
        safe_stderr = redact_secrets(e.stderr or "")
        raise RuntimeError(f"git push failed: {safe_msg} {safe_stderr}") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("git push timed out (120s)") from None

    return sha


def parse_github_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo name from GitHub URL."""
    match = re.search(r"github\.com/([^/]+)/([^/.]+)", repo_url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {repo_url}")
    return match.group(1), match.group(2)


def redact_state(state: dict) -> dict:
    """Remove secrets before persisting or broadcasting."""
    return {k: v for k, v in state.items() if k != "github_token"}
