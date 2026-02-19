from datetime import datetime, timezone
from app.api.websocket import manager


class HealingCallback:
    """Broadcasts LangGraph node progress to WebSocket clients."""

    def __init__(self, run_id: str):
        self.run_id = run_id

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def on_node_start(self, node_name: str, message: str):
        await manager.broadcast(self.run_id, {
            "event_type": "node_start",
            "run_id": self.run_id,
            "node": node_name,
            "message": message,
            "data": None,
            "timestamp": self._now(),
        })

    async def on_node_end(self, node_name: str, message: str, data: dict = None):
        await manager.broadcast(self.run_id, {
            "event_type": "node_end",
            "run_id": self.run_id,
            "node": node_name,
            "message": message,
            "data": data,
            "timestamp": self._now(),
        })

    async def on_progress(self, message: str, data: dict = None):
        await manager.broadcast(self.run_id, {
            "event_type": "progress",
            "run_id": self.run_id,
            "node": None,
            "message": message,
            "data": data,
            "timestamp": self._now(),
        })

    async def on_complete(self, message: str, data: dict = None):
        await manager.broadcast(self.run_id, {
            "event_type": "complete",
            "run_id": self.run_id,
            "node": None,
            "message": message,
            "data": data,
            "timestamp": self._now(),
        })

    async def on_error(self, message: str, data: dict = None):
        await manager.broadcast(self.run_id, {
            "event_type": "error",
            "run_id": self.run_id,
            "node": None,
            "message": message,
            "data": data,
            "timestamp": self._now(),
        })
