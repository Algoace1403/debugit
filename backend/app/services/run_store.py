import json
import asyncio
from pathlib import Path
from app.config import settings


class RunStore:
    """Disk-backed run storage with in-memory index."""

    def __init__(self):
        self._index: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._data_dir = Path(settings.data_dir)

    def _lock(self, run_id: str) -> asyncio.Lock:
        if run_id not in self._locks:
            self._locks[run_id] = asyncio.Lock()
        return self._locks[run_id]

    def _run_dir(self, run_id: str) -> Path:
        return self._data_dir / run_id

    def _write_json(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _read_json(self, path: Path) -> dict:
        with open(path) as f:
            return json.load(f)

    async def create(self, run_id: str, initial_state: dict):
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)
        async with self._lock(run_id):
            self._write_json(run_dir / "state.json", initial_state)
            self._index[run_id] = {"status": "running", "dir": str(run_dir)}

    async def update_state(self, run_id: str, partial: dict):
        async with self._lock(run_id):
            run_dir = self._run_dir(run_id)
            state_path = run_dir / "state.json"
            if not state_path.exists():
                return
            state = self._read_json(state_path)
            for k, v in partial.items():
                if isinstance(v, list) and isinstance(state.get(k), list):
                    state[k] = state[k] + v
                else:
                    state[k] = v
            self._write_json(state_path, state)

    async def save_results(self, run_id: str, results: dict):
        async with self._lock(run_id):
            run_dir = self._run_dir(run_id)
            self._write_json(run_dir / "results.json", results)

    async def get_state(self, run_id: str) -> dict | None:
        state_path = self._run_dir(run_id) / "state.json"
        if not state_path.exists():
            return None
        return self._read_json(state_path)

    async def get_results(self, run_id: str) -> dict | None:
        results_path = self._run_dir(run_id) / "results.json"
        if not results_path.exists():
            return None
        return self._read_json(results_path)

    async def set_status(self, run_id: str, status: str):
        if run_id in self._index:
            self._index[run_id]["status"] = status

    async def list_runs(self) -> list[dict]:
        return [{"run_id": k, **v} for k, v in self._index.items()]


run_store = RunStore()
