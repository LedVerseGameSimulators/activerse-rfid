"""
Activerse RFID Server — FastAPI backend.
Reception/admin hub for LED floor game kiosk.
"""
import asyncio

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import API_HOST, API_PORT
from .database import get_db
from . import players, sessions, dashboard
from . import poller as poller_mod
from .models import (
    PlayerCreate, PlayerUpdate, BindCardRequest,
    SessionCreate, SessionAdjust, LoginRequest, ChangePasswordRequest,
)

app = FastAPI(title="Activerse RFID Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_poller_task = None


@app.on_event("startup")
async def startup():
    global _poller_task
    db = get_db()
    logger.info("RFID server starting — tables ensured")
    _poller_task = asyncio.create_task(poller_mod.poller_loop(db))


@app.on_event("shutdown")
async def shutdown():
    poller_mod.stop_poller()
    if _poller_task:
        _poller_task.cancel()


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "activerse-rfid"}


# ── Auth / Settings ───────────────────────────────────────────────────────

@app.post("/auth/login")
async def auth_login(body: LoginRequest):
    db = get_db()
    if db.verify_login(body.username, body.password):
        return {"success": True}
    return {"success": False, "error": "Invalid credentials"}


@app.post("/auth/change-password")
async def change_password(body: ChangePasswordRequest):
    db = get_db()
    db.change_admin_password(body.username, body.password)
    return {"success": True}


# ── Players ───────────────────────────────────────────────────────────────

@app.get("/players")
async def list_players(q: str = Query(default="")):
    return players.list_players(get_db(), q)


@app.post("/players")
async def create_player(body: PlayerCreate):
    return players.register_player(
        get_db(), body.name, body.phone, body.email, body.age, body.public, body.notes
    )


@app.get("/players/{player_id}")
async def get_player(player_id: int):
    return players.get_player(get_db(), player_id)


@app.put("/players/{player_id}")
async def update_player(player_id: int, body: PlayerUpdate):
    return players.update_player(
        get_db(), player_id,
        name=body.name, email=body.email, age=body.age,
        public=body.public, notes=body.notes,
    )


@app.delete("/players/{player_id}")
async def delete_player(player_id: int):
    return players.delete_player(get_db(), player_id)


@app.post("/players/{player_id}/bind-card")
async def bind_card(player_id: int, body: BindCardRequest):
    return players.bind_card(get_db(), player_id, body.card_id)


@app.post("/players/{player_id}/unbind-card")
async def unbind_card(player_id: int):
    return players.unbind_card(get_db(), player_id)


# ── Sessions ──────────────────────────────────────────────────────────────

@app.post("/sessions")
async def create_session(body: SessionCreate):
    return sessions.issue_session(get_db(), body.player_id, body.duration_min, body.notes or "")


@app.get("/sessions/active")
async def active_sessions():
    return sessions.get_active_sessions(get_db())


@app.get("/sessions/{session_id}")
async def get_session(session_id: int):
    return sessions.get_session_detail(get_db(), session_id)


@app.post("/sessions/{session_id}/adjust")
async def adjust_session(session_id: int, body: SessionAdjust):
    return sessions.adjust_session(
        get_db(), session_id, body.delta_min, body.reason, body.adjusted_by
    )


@app.post("/sessions/{session_id}/close")
async def close_session(session_id: int):
    return sessions.close_session(get_db(), session_id)


@app.get("/validate")
async def validate(card_id: str = Query(...)):
    """Called by game machines — no auth required."""
    return sessions.validate_card(get_db(), card_id)


# ── Dashboard ─────────────────────────────────────────────────────────────

@app.get("/dashboard/health")
async def dash_health():
    return dashboard.get_health(get_db())


@app.get("/dashboard/leaderboard")
async def dash_leaderboard(
    game: str = Query(default="all"),
    period: str = Query(default="alltime"),
    limit: int = Query(default=20, le=100),
):
    return dashboard.get_leaderboard(get_db(), game, period, limit)


@app.get("/dashboard/stats")
async def dash_stats():
    return dashboard.get_stats(get_db())


@app.get("/dashboard/player/{player_id}")
async def dash_player(player_id: int):
    return dashboard.get_player_dashboard(get_db(), player_id)


# ── Internal ──────────────────────────────────────────────────────────────

@app.post("/internal/poll-now")
async def poll_now():
    await poller_mod.poll_all(get_db())
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host=API_HOST, port=API_PORT, reload=False)
