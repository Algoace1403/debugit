import os

from app.models.state import HealingState
from app.services.github_service import make_branch_name, clone_repo, create_branch
from app.services.sandbox import install_deps
from app.utils.framework_detector import (
    detect_language,
    detect_package_manager,
    detect_test_framework,
    discover_test_files,
)
from app.services.github_service import redact_secrets
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("repo_analyzer")


async def repo_analyzer_node(state: HealingState) -> dict:
    """
    Clone repo, detect language/framework, discover test files,
    install dependencies, create feature branch.
    """
    run_id = state.get("run_id", "unknown")
    repo_url = state.get("repo_url", "")
    team_name = state.get("team_name", "")
    leader_name = state.get("leader_name", "")

    # Branch naming — spec-exact format
    branch_name = make_branch_name(team_name, leader_name)
    repo_path = os.path.join(settings.data_dir, run_id, "repo")

    logger.info(f"Repo: {repo_url}, Branch: {branch_name}, Path: {repo_path}")

    try:
        # 1. Clone
        os.makedirs(os.path.dirname(repo_path), exist_ok=True)
        clone_repo(repo_url, repo_path)
        logger.info("Clone complete")

        # 2. Detect language, package manager, test framework
        language = detect_language(repo_path)
        package_manager = detect_package_manager(repo_path)
        test_framework = detect_test_framework(repo_path, language)
        test_files = discover_test_files(repo_path, language)

        logger.info(
            f"Detected: lang={language}, pkg={package_manager}, "
            f"framework={test_framework}, test_files={len(test_files)}"
        )

        # 3. Build a basic project_structure summary
        project_structure = _build_project_structure(repo_path)

        # 4. Install dependencies
        try:
            result = install_deps(repo_path, package_manager)
            if result.returncode != 0:
                logger.warning(f"Dependency install exited {result.returncode}: {result.stderr[:500]}")
            else:
                logger.info("Dependencies installed")
        except Exception as e:
            logger.warning(f"Dependency install failed (continuing): {e}")

        # 5. Create feature branch
        create_branch(repo_path, branch_name)
        logger.info(f"Created branch: {branch_name}")

        return {
            "repo_path": repo_path,
            "branch_name": branch_name,
            "language": language,
            "test_framework": test_framework,
            "package_manager": package_manager,
            "test_files": test_files,
            "project_structure": project_structure,
            "current_node": "repo_analyzer",
            "status_message": (
                f"Cloned. {language}/{test_framework}, "
                f"{len(test_files)} test files, branch: {branch_name}"
            ),
        }

    except Exception as e:
        safe_error = redact_secrets(str(e))
        logger.error(f"repo_analyzer failed: {safe_error}")
        return {
            "repo_path": repo_path,
            "branch_name": branch_name,
            "language": "",
            "test_framework": "",
            "package_manager": "",
            "test_files": [],
            "project_structure": {},
            "current_node": "repo_analyzer",
            "status_message": f"repo_analyzer error: {safe_error}",
            "error": safe_error,
        }


def _build_project_structure(repo_path: str) -> dict:
    """Build a lightweight summary of the repo layout."""
    structure: dict = {"files_count": 0, "dirs": []}
    try:
        for entry in os.listdir(repo_path):
            full = os.path.join(repo_path, entry)
            if entry.startswith("."):
                continue
            if os.path.isdir(full) and entry not in ("node_modules", "__pycache__", "venv", ".venv"):
                structure["dirs"].append(entry)
            elif os.path.isfile(full):
                structure["files_count"] += 1
    except OSError:
        pass
    return structure
