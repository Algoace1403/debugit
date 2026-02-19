import subprocess
import shutil
import sys
import os

from app.utils.logger import get_logger

logger = get_logger("sandbox")

SANDBOX_IMAGE = "cihealer-sandbox:latest"


def _detect_local_python() -> str:
    """Detect the Python executable for subprocess fallback (non-Docker)."""
    if shutil.which("python3"):
        return "python3"
    if shutil.which("python"):
        return "python"
    return sys.executable


_LOCAL_PYTHON = _detect_local_python()


def _adapt_command_for_local(command: str) -> str:
    """Replace python/pip references with detected local executables.

    Only used in the subprocess fallback path — Docker commands are unchanged.
    Handles macOS where only python3/pip3 exist (no python/pip).
    """
    if _LOCAL_PYTHON == "python":
        return command
    cmd = command.replace("python -m ", f"{_LOCAL_PYTHON} -m ")
    cmd = cmd.replace("pip install ", f"{_LOCAL_PYTHON} -m pip install ")
    return cmd


def _check_docker_available() -> bool:
    """Check if Docker binary exists AND the sandbox image is built."""
    if not shutil.which("docker"):
        return False
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", SANDBOX_IMAGE],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            logger.info(f"Docker sandbox available: {SANDBOX_IMAGE}")
            return True
        else:
            logger.info(f"Docker found but sandbox image '{SANDBOX_IMAGE}' not built — using subprocess fallback")
            return False
    except Exception:
        logger.info("Docker check failed — using subprocess fallback")
        return False


DOCKER_AVAILABLE = _check_docker_available()


def run_in_sandbox(
    repo_path: str,
    command: str,
    timeout: int = 120,
    network: bool = False,
) -> subprocess.CompletedProcess:
    """Run command inside Docker with resource limits."""
    docker_cmd = [
        "docker", "run", "--rm",
        "--memory=512m",
        "--cpus=1",
        "--pids-limit=256",
        "-v", f"{os.path.abspath(repo_path)}:/workspace",
        "-w", "/workspace",
    ]
    if not network:
        docker_cmd.append("--network=none")
    docker_cmd += [SANDBOX_IMAGE, "bash", "-c", command]

    return subprocess.run(
        docker_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_command(
    repo_path: str,
    command: str,
    timeout: int = 120,
    network: bool = False,
) -> subprocess.CompletedProcess:
    """Run command — Docker if available, otherwise direct subprocess."""
    if DOCKER_AVAILABLE:
        return run_in_sandbox(repo_path, command, timeout, network)
    else:
        local_cmd = _adapt_command_for_local(command)
        return subprocess.run(
            ["bash", "-c", local_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_path,
        )


def install_deps(repo_path: str, package_manager: str) -> subprocess.CompletedProcess:
    """Install dependencies WITH network access."""
    cmds = {
        "pip": "pip install -r requirements.txt 2>&1 || pip install -e . 2>&1",
        "npm": "npm ci 2>&1 || npm install 2>&1",
        "pnpm": "pnpm install --frozen-lockfile 2>&1 || pnpm install 2>&1",
        "yarn": "yarn install --frozen-lockfile 2>&1 || yarn install 2>&1",
    }
    cmd = cmds.get(package_manager, cmds["pip"])
    logger.info(f"Installing deps with {package_manager}: {cmd[:80]}...")
    return run_command(repo_path, cmd, timeout=180, network=True)


def run_tests(repo_path: str, test_command: str) -> subprocess.CompletedProcess:
    """Run tests WITHOUT network access."""
    logger.info(f"Running tests: {test_command[:80]}...")
    return run_command(repo_path, test_command, timeout=120, network=False)
