from __future__ import annotations

from pathlib import Path
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .agent import JarvisAgent
from .config import AppPaths
from .ingest import ingest_path
from .memory import MemoryStore
from .profile import ProfileStore


class ChatRequest(BaseModel):
    message: str


class ProfileRequest(BaseModel):
    key: str
    value: str


class IngestRequest(BaseModel):
    path: str


def create_app(agent: JarvisAgent, paths: AppPaths, memory: MemoryStore, profile: ProfileStore) -> FastAPI:
    app = FastAPI(title="Jarvis Local Agent")
    templates = Jinja2Templates(directory=str(paths.templates_dir))
    app.mount("/static", StaticFiles(directory=str(paths.static_dir)), name="static")
    csrf_token = secrets.token_urlsafe(32)

    def require_token(request: Request) -> None:
        header = request.headers.get("X-Jarvis-Token", "")
        if not header or header != csrf_token:
            raise HTTPException(status_code=403, detail="Missing or invalid CSRF token.")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            name="index.html",
            request=request,
            context={
                "request": request,
                "app_name": "Jarvis",
                "model_name": agent.model_name or "offline",
                "csrf_token": csrf_token,
            },
        )

    @app.get("/api/state")
    async def state() -> dict:
        return {
            "profile": profile.load(),
            "dashboard": memory.dashboard_state(),
            "model_name": agent.model_name,
        }

    @app.get("/api/history")
    async def history(query: str = "") -> dict:
        if query:
            return {"items": memory.search_activities(query, limit=10)}
        return {"items": memory.recent_activities(12)}

    @app.post("/api/chat")
    async def chat(payload: ChatRequest, request: Request) -> dict:
        require_token(request)
        if not payload.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty.")
        if len(payload.message) > 8000:
            raise HTTPException(status_code=413, detail="Message is too long.")
        return agent.handle(payload.message)

    @app.post("/api/profile")
    async def update_profile(payload: ProfileRequest, request: Request) -> dict:
        require_token(request)
        if len(payload.key) > 120 or len(payload.value) > 4000:
            raise HTTPException(status_code=413, detail="Profile value is too long.")
        updated = profile.set(payload.key, payload.value)
        return {"profile": updated}

    @app.post("/api/ingest")
    async def ingest(payload: IngestRequest, request: Request) -> dict:
        require_token(request)
        if len(payload.path) > 512:
            raise HTTPException(status_code=413, detail="Path is too long.")
        target = Path(payload.path).expanduser()
        if not target.exists():
            raise HTTPException(status_code=404, detail="Path not found.")
        stored = ingest_path(memory, target)
        return {"count": len(stored), "stored": stored[:20]}

    return app
