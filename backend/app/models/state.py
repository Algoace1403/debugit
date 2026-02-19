from typing import TypedDict, Annotated, Literal, Optional
import operator

BugType = Literal["LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION"]


class TestFailure(TypedDict):
    test_file: str
    test_name: str
    error_message: str
    traceback: str
    source_file: str
    source_line: int


class Classification(TypedDict):
    bug_type: str  # BugType
    file: str
    line: int
    fix_summary: str
    issue_line: str
    confidence: float
    root_cause: str
    method: str  # "RULE" or "LLM"


class AppliedFix(TypedDict):
    file: str
    bug_type: str
    line_number: int
    issue_line: str
    commit_message: str
    status: str  # "fixed" or "failed"
    diff: str
    iteration: int


class CIRun(TypedDict):
    iteration: int
    status: str  # "PASSED" or "FAILED"
    mode: str  # "CI" or "LOCAL_ONLY"
    run_url: str
    timestamp: str
    failures_remaining: int


class HealingState(TypedDict):
    # Inputs
    repo_url: str
    team_name: str
    leader_name: str
    github_token: str  # FROM ENV ONLY
    run_id: str

    # Repo analysis
    repo_path: str
    branch_name: str
    language: str
    test_framework: str
    package_manager: str
    test_files: list[str]
    project_structure: dict

    # Test results (latest iteration)
    total_tests: int
    passed_tests: int
    failed_tests: int
    failures: list[TestFailure]
    all_tests_passing: bool

    # Classifications (current iteration)
    classifications: list[Classification]

    # Proposed fixes (current iteration, from fix_generator → fix_validator)
    proposed_fixes: list[dict]

    # Fix tracking (accumulated across iterations)
    fixes_applied: Annotated[list[AppliedFix], operator.add]

    # Git
    last_commit_sha: str
    total_commits: int

    # CI
    ci_runs: Annotated[list[CIRun], operator.add]
    ci_passed: bool

    # Loop control
    iteration: int
    max_iterations: int

    # Scoring
    start_time: str
    end_time: Optional[str]
    duration_seconds: float
    score: dict

    # Progress
    current_node: str
    status_message: str
    error: Optional[str]
