from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.auth import auth_router
from app.api.websocket import websocket_endpoint
from app.config import settings

app = FastAPI(title="CI/CD Healing Agent", version="1.0.0")

# Parse ALLOWED_ORIGINS: comma-separated string → list
_raw = settings.allowed_origins.strip()
if _raw in ("*", ""):
    _origins = ["*"]
else:
    _origins = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.add_api_websocket_route("/ws/{run_id}", websocket_endpoint)
