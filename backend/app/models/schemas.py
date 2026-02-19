from pydantic import BaseModel
from typing import Optional


class HealRequest(BaseModel):
    repo_url: str
    team_name: str
    leader_name: str


class HealResponse(BaseModel):
    run_id: str
    status: str


class FixEntry(BaseModel):
    file: str
    bug_type: str
    line_number: int
    issue_line: str
    commit_message: str
    status: str  # "fixed" or "failed"
    diff: str
    iteration: int


class CIRunEntry(BaseModel):
    iteration: int
    status: str  # "PASSED" or "FAILED"
    mode: str  # "CI" or "LOCAL_ONLY"
    run_url: str
    timestamp: str
    failures_remaining: int


class ScoreBreakdown(BaseModel):
    base: int = 100
    speed_bonus: int = 0
    efficiency_penalty: int = 0
    total: int = 100


class ResultsJson(BaseModel):
    repo_url: str
    team_name: str
    leader_name: str
    branch_name: str
    start_time: str
    end_time: Optional[str] = None
    total_time_seconds: float = 0
    total_failures_detected: int = 0
    total_fixes_applied: int = 0
    total_commits: int = 0
    final_status: str = "FAILED"  # "PASSED" or "FAILED"
    score: ScoreBreakdown = ScoreBreakdown()
    fixes: list[FixEntry] = []
    ci_runs: list[CIRunEntry] = []


class WSEvent(BaseModel):
    event_type: str  # "node_start", "node_end", "progress", "error", "complete"
    run_id: str
    node: Optional[str] = None
    message: str
    data: Optional[dict] = None
    timestamp: str = ""
