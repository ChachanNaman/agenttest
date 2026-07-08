"""FastAPI application entry point for the agenttest backend."""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_PORT = 8000


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line, no external dependency."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(BACKEND_DIR.parent / ".env")

from fastapi import FastAPI, WebSocket  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.routes import benchmark, compare, history, runs, snapshots  # noqa: E402
from api.websocket import handle_run_socket  # noqa: E402
from core import storage  # noqa: E402

app = FastAPI(title="Agenttest", description="A testing framework for LLM agents and tool-calling")

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(benchmark.router, prefix="/api")
app.include_router(snapshots.router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    storage.init_db()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/run")
async def ws_run(websocket: WebSocket) -> None:
    await handle_run_socket(websocket)


static_dir = BACKEND_DIR / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", DEFAULT_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
