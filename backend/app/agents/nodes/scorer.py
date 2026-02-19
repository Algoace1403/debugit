from datetime import datetime, timezone

from app.models.state import HealingState
from app.services.scoring import calculate_score
from app.utils.logger import get_logger

logger = get_logger("scorer")


async def scorer_node(state: HealingState) -> dict:
    """Calculate final score and set end_time."""
    start_str = state.get("start_time", "")
    now = datetime.now(timezone.utc)
    end_time = now.isoformat()

    # Calculate duration
    if start_str:
        try:
            start = datetime.fromisoformat(start_str)
            duration = (now - start).total_seconds()
        except (ValueError, TypeError):
            duration = 0.0
    else:
        duration = 0.0

    total_commits = state.get("total_commits", 0)
    score = calculate_score(duration, total_commits)

    logger.info(
        f"Final score: {score['total']} "
        f"(base={score['base']}, speed_bonus={score['speed_bonus']}, "
        f"penalty={score['efficiency_penalty']}, "
        f"duration={duration:.0f}s, commits={total_commits})"
    )

    return {
        "end_time": end_time,
        "duration_seconds": duration,
        "score": score,
        "current_node": "scorer",
        "status_message": f"Score: {score['total']} ({duration:.0f}s, {total_commits} commits)",
    }
