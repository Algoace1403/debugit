import os
import json
import glob as glob_mod


def detect_language(repo_path: str) -> str:
    """Detect dominant language by file extension counts."""
    py_count = _count_files(repo_path, [".py"])
    js_count = _count_files(repo_path, [".js", ".jsx"])
    ts_count = _count_files(repo_path, [".ts", ".tsx"])

    total_js = js_count + ts_count
    if py_count > 0 and total_js > 0:
        return "mixed"
    if py_count > 0:
        return "python"
    if ts_count > js_count:
        return "typescript"
    if total_js > 0:
        return "javascript"
    return "python"  # fallback


def detect_package_manager(repo_path: str) -> str:
    if os.path.exists(os.path.join(repo_path, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(repo_path, "yarn.lock")):
        return "yarn"
    if os.path.exists(os.path.join(repo_path, "package-lock.json")):
        return "npm"
    if os.path.exists(os.path.join(repo_path, "requirements.txt")) or \
       os.path.exists(os.path.join(repo_path, "pyproject.toml")):
        return "pip"
    return "pip"


def detect_test_framework(repo_path: str, language: str) -> str:
    if language in ("python", "mixed"):
        if os.path.exists(os.path.join(repo_path, "conftest.py")):
            return "pytest"
        if os.path.exists(os.path.join(repo_path, "pytest.ini")):
            return "pytest"
        if _file_contains(os.path.join(repo_path, "pyproject.toml"), "[tool.pytest"):
            return "pytest"
        if _file_contains(os.path.join(repo_path, "setup.cfg"), "[tool:pytest]"):
            return "pytest"
        return "pytest"  # default for Python

    if language in ("javascript", "typescript", "mixed"):
        pkg_path = os.path.join(repo_path, "package.json")
        if os.path.exists(pkg_path):
            with open(pkg_path) as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            scripts = pkg.get("scripts", {})

            if "vitest" in deps or "vitest" in scripts.get("test", ""):
                return "vitest"
            if "jest" in deps or "jest" in scripts.get("test", ""):
                return "jest"
            if "mocha" in deps or "mocha" in scripts.get("test", ""):
                return "mocha"

        if glob_mod.glob(os.path.join(repo_path, "jest.config.*")):
            return "jest"
        if glob_mod.glob(os.path.join(repo_path, ".mocharc.*")):
            return "mocha"
        if glob_mod.glob(os.path.join(repo_path, "vitest.config.*")):
            return "vitest"
        return "jest"  # default for JS

    return "pytest"


def get_test_command(framework: str, package_manager: str, test_files: list[str] | None = None) -> str:
    """Return the test execution command for the detected framework.

    For pytest: if test_files are provided, append them so pytest discovers
    tests in non-standard filenames (e.g. main.py with def test_ functions).
    """
    if framework in ("pytest", "unittest"):
        # Build file list arg for pytest (handles non-standard names like main.py)
        file_args = ""
        if test_files:
            file_args = " " + " ".join(test_files)
        return (
            f"python -m pytest{file_args} --tb=long -v "
            f"--json-report --json-report-file=report.json 2>&1 "
            f"|| python -m pytest{file_args} --tb=long -v 2>&1"
        )

    commands = {
        "jest_npm": "npx jest --verbose 2>&1",
        "jest_pnpm": "pnpm exec jest --verbose 2>&1",
        "jest_yarn": "yarn jest --verbose 2>&1",
        "mocha_npm": "npx mocha --reporter spec 2>&1",
        "vitest_npm": "npx vitest run --reporter=verbose 2>&1",
    }

    key = f"{framework}_{package_manager}"
    return commands.get(key, commands.get(f"{framework}_npm", "npm test 2>&1"))


def discover_test_files(repo_path: str, language: str) -> list[str]:
    """Find all test files by naming conventions, with fallback for non-standard names."""
    patterns = {
        "python": ["**/test_*.py", "**/*_test.py", "**/tests.py"],
        "javascript": ["**/*.test.js", "**/*.spec.js", "**/__tests__/**/*.js"],
        "typescript": ["**/*.test.ts", "**/*.spec.ts", "**/*.test.tsx", "**/*.spec.tsx",
                       "**/__tests__/**/*.ts"],
        "mixed": ["**/test_*.py", "**/*_test.py", "**/tests.py",
                  "**/*.test.js", "**/*.test.ts", "**/*.spec.js", "**/*.spec.ts"],
    }
    excludes = {"node_modules", ".git", "dist", "build", "__pycache__", "venv", ".venv"}

    found = []
    for pattern in patterns.get(language, patterns["python"]):
        for path in glob_mod.glob(os.path.join(repo_path, pattern), recursive=True):
            # Skip excluded directories
            parts = path.split(os.sep)
            if any(ex in parts for ex in excludes):
                continue
            # Store relative path
            found.append(os.path.relpath(path, repo_path))

    # Fallback: if no test files found by naming convention, scan all .py files
    # for functions named "def test_" (common in small/hackathon repos)
    if not found and language in ("python", "mixed"):
        for path in glob_mod.glob(os.path.join(repo_path, "**/*.py"), recursive=True):
            parts = path.split(os.sep)
            if any(ex in parts for ex in excludes):
                continue
            try:
                with open(path) as f:
                    content = f.read()
                if "def test_" in content:
                    found.append(os.path.relpath(path, repo_path))
            except OSError:
                continue

    return sorted(set(found))


def _count_files(repo_path: str, extensions: list[str]) -> int:
    count = 0
    for root, dirs, files in os.walk(repo_path):
        # Skip common non-source dirs
        dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "venv", ".venv", "__pycache__"}]
        for f in files:
            if any(f.endswith(ext) for ext in extensions):
                count += 1
    return count


def _file_contains(filepath: str, needle: str) -> bool:
    if not os.path.exists(filepath):
        return False
    with open(filepath) as f:
        return needle in f.read()
