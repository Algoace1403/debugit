def calculate_score(duration_seconds: float, total_commits: int) -> dict:
    base = 100
    speed_bonus = 10 if duration_seconds < 300 else 0
    efficiency_penalty = max(0, (total_commits - 20)) * 2
    total = max(0, base + speed_bonus - efficiency_penalty)

    return {
        "base": base,
        "speed_bonus": speed_bonus,
        "efficiency_penalty": efficiency_penalty,
        "total": total,
    }


def format_issue_line(bug_type: str, file: str, line: int, fix_summary: str) -> str:
    """Canonical format — backend generates, frontend renders verbatim."""
    assert bug_type in ("LINTING", "SYNTAX", "LOGIC", "TYPE_ERROR", "IMPORT", "INDENTATION")
    return f"{bug_type} error in {file} line {line} \u2192 Fix: {fix_summary}"
