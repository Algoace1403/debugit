import asyncio
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.run_store import run_store
from app.agents.orchestrator import run_healing_pipeline

router = APIRouter(prefix="/api/v1")


class HealRequest(BaseModel):
    repo_url: str
    team_name: str
    leader_name: str
    # NOTE: NO github_token field — token comes from env only


class HealResponse(BaseModel):
    run_id: str
    status: str


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/heal", response_model=HealResponse)
async def start_healing(request: HealRequest):
    run_id = str(uuid.uuid4())

    # Launch pipeline as background task (fire-and-forget)
    asyncio.create_task(
        run_healing_pipeline(
            run_id=run_id,
            repo_url=request.repo_url,
            team_name=request.team_name,
            leader_name=request.leader_name,
        )
    )

    return HealResponse(run_id=run_id, status="running")


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    state = await run_store.get_state(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Run not found")

    results = await run_store.get_results(run_id)
    return {
        "run_id": run_id,
        "status": state.get("status", "running"),
        "current_node": state.get("current_node", ""),
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 5),
        "error": state.get("error"),
        "results": results,
    }


@router.get("/runs/{run_id}/results")
async def get_results(run_id: str):
    results = await run_store.get_results(run_id)
    if results is None:
        raise HTTPException(status_code=404, detail="Results not found")
    return results


@router.get("/runs")
async def list_runs():
    runs = await run_store.list_runs()
    return {"runs": runs}
