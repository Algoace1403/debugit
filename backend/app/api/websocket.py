from fastapi import WebSocket, WebSocketDisconnect
import json
from datetime import datetime, timezone


class ConnectionManager:
    """Manages WebSocket connections keyed by run_id."""

    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(run_id, []).append(websocket)

    async def disconnect(self, run_id: str, websocket: WebSocket):
        conns = self.connections.get(run_id, [])
        if websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, run_id: str, event: dict):
        """Send event JSON to all clients connected to this run_id."""
        dead = []
        for ws in self.connections.get(run_id, []):
            try:
                await ws.send_json(event)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(run_id, ws)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, run_id: str):
    await manager.connect(run_id, websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await websocket.receive_text()
            # Echo back as acknowledgment
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        await manager.disconnect(run_id, websocket)
