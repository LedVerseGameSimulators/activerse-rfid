"""
Activerse RFID Server — FastAPI backend.
Reception/admin hub for LED floor game kiosk.
"""
import asyncio

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .config import API_HOST, API_PORT, GAME_REGISTRY
from .database import get_db
from . import players, sessions, dashboard, companies, groups, tournaments as tournaments_mod
from . import poller as poller_mod
from . import import_excel as import_excel_mod
from .models import (
    PlayerCreate, PlayerUpdate, BindCardRequest, TopUpRequest,
    SessionCreate, SessionAdjust, LoginRequest, ChangePasswordRequest,
    GameSettingsPush, RosterAddRequest,
    CompanyCreate, CompanyUpdate, GroupCreate, GroupUpdate,
    GroupMemberAdd, GroupMemberTransfer, GroupLeaderSet, StartVisitRequest,
    TournamentCreate, TournamentUpdate, ActivateGlobal,
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


# ── Settings (Task 3.1/3.2: money/time ratios + per-game push) ─────────────

@app.get("/settings")
async def get_settings():
    return get_db().get_all_settings()


@app.put("/settings")
async def update_settings(body: dict):
    db = get_db()
    for k, v in body.items():
        db.set_setting(k, str(v))
    return db.get_all_settings()


@app.put("/games/{game_key}/settings")
async def push_game_settings(game_key: str, body: GameSettingsPush):
    if game_key not in GAME_REGISTRY:
        raise HTTPException(404, f"Unknown game: {game_key}")
    base_url = GAME_REGISTRY[game_key]["api"]
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.post(f"{base_url}/settings", json={
                "default_difficulty": body.default_difficulty,
                "session_minutes": body.session_minutes,
            })
            resp.raise_for_status()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Could not reach {game_key}: {e}")
    get_db().push_game_settings(game_key, body.default_difficulty, body.session_minutes)
    return {"success": True}


@app.get("/games/{game_key}/settings")
async def get_pushed_game_settings(game_key: str):
    if game_key not in GAME_REGISTRY:
        raise HTTPException(404, f"Unknown game: {game_key}")
    return get_db().get_pushed_game_settings(game_key) or {}


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


@app.post("/players/{player_id}/topup")
async def topup_player(player_id: int, body: TopUpRequest):
    return players.topup_player(get_db(), player_id, body.minutes, body.amount_money or 0)


@app.post("/players/{player_id}/ensure-solo-group")
async def ensure_player_solo_group(player_id: int):
    return players.ensure_solo_group(get_db(), player_id)


# ── Sessions ──────────────────────────────────────────────────────────────

@app.post("/sessions")
async def create_session(body: SessionCreate):
    return sessions.issue_session_retired()


@app.get("/sessions/active")
async def active_sessions():
    return sessions.get_active_sessions(get_db())


@app.get("/sessions/{session_id}")
async def get_session(session_id: int):
    return sessions.get_session_detail(get_db(), session_id)


@app.post("/sessions/{session_id}/adjust")
async def adjust_session(session_id: int, body: SessionAdjust):
    return sessions.adjust_session(
        get_db(),
        session_id,
        body.delta_min,
        body.reason,
        body.adjusted_by,
        adjustment_mode=body.adjustment_mode,
        balance_delta_min=body.balance_delta_min,
    )


@app.post("/sessions/{session_id}/close")
async def close_session(session_id: int):
    return sessions.close_session(get_db(), session_id)


@app.get("/sessions/{session_id}/roster")
async def get_roster(session_id: int):
    return sessions.get_roster(get_db(), session_id)


@app.post("/sessions/{session_id}/roster")
async def add_roster_member(session_id: int, body: RosterAddRequest):
    return sessions.add_roster_member(get_db(), session_id, body.player_id)


@app.delete("/sessions/{session_id}/roster/{player_id}")
async def remove_roster_member(session_id: int, player_id: int):
    return sessions.remove_roster_member(get_db(), session_id, player_id)


@app.get("/validate")
async def validate(card_id: str = Query(...)):
    """Called by game machines — no auth required."""
    return sessions.validate_card(get_db(), card_id)


# ── Companies / Groups ────────────────────────────────────────────────────

@app.get("/companies")
async def list_companies():
    return companies.list_companies(get_db())


@app.post("/companies")
async def create_company(body: CompanyCreate):
    return companies.create_company(get_db(), body.name, body.notes or "")


@app.get("/companies/{company_id}")
async def get_company(company_id: int):
    return companies.get_company(get_db(), company_id)


@app.put("/companies/{company_id}")
async def update_company(company_id: int, body: CompanyUpdate):
    return companies.update_company(get_db(), company_id, name=body.name, notes=body.notes)


@app.delete("/companies/{company_id}")
async def delete_company(company_id: int):
    return companies.delete_company(get_db(), company_id)


@app.get("/companies/{company_id}/members")
async def list_company_members(company_id: int):
    return companies.list_members(get_db(), company_id)


@app.delete("/companies/{company_id}/members/{player_id}")
async def leave_company(company_id: int, player_id: int):
    return companies.leave_company(get_db(), company_id, player_id)


@app.get("/groups")
async def list_groups(company_id: int | None = Query(default=None),
                      walk_in_only: bool = Query(default=False),
                      include_archived: bool = Query(default=False)):
    return groups.list_groups(
        get_db(), company_id, walk_in_only=walk_in_only, include_archived=include_archived,
    )


@app.post("/groups")
async def create_group(body: GroupCreate):
    return groups.create_group(get_db(), body.company_id, body.name, body.leader_player_id)


@app.get("/groups/{group_id}")
async def get_group(group_id: int):
    return groups.get_group(get_db(), group_id)


@app.put("/groups/{group_id}")
async def update_group(group_id: int, body: GroupUpdate):
    return groups.update_group(get_db(), group_id, name=body.name)


@app.delete("/groups/{group_id}")
async def delete_group(group_id: int):
    return groups.delete_group(get_db(), group_id)


@app.post("/groups/{group_id}/archive")
async def archive_group(group_id: int):
    return groups.archive_group(get_db(), group_id)


@app.post("/groups/{group_id}/unarchive")
async def unarchive_group(group_id: int):
    return groups.unarchive_group(get_db(), group_id)


@app.post("/groups/{group_id}/members")
async def add_group_member(group_id: int, body: GroupMemberAdd):
    return groups.add_member(
        get_db(), group_id,
        player_id=body.player_id, name=body.name, phone=body.phone,
        email=body.email, age=body.age,
    )


@app.delete("/groups/{group_id}/members/{player_id}")
async def remove_group_member(group_id: int, player_id: int):
    return groups.remove_member(get_db(), group_id, player_id)


@app.post("/groups/{group_id}/members/transfer")
async def transfer_group_member(group_id: int, body: GroupMemberTransfer):
    return groups.transfer_member(get_db(), group_id, body.player_id)


@app.put("/groups/{group_id}/leader")
async def set_group_leader(group_id: int, body: GroupLeaderSet):
    return groups.set_leader(get_db(), group_id, body.player_id)


@app.post("/groups/{group_id}/start-visit")
async def start_group_visit(group_id: int, body: StartVisitRequest):
    return groups.start_visit(get_db(), group_id, body.duration_min, body.card_id)


# ── Excel import ──────────────────────────────────────────────────────────

@app.get("/import/template.xlsx")
async def download_import_template():
    from fastapi.responses import Response
    data = import_excel_mod.build_template_bytes()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=activerse_import_template.xlsx"},
    )


@app.post("/import/excel")
async def import_excel(file: UploadFile = File(...)):
    return import_excel_mod.import_excel(get_db(), file)


@app.get("/companies/{company_id}/import/template.xlsx")
async def download_company_import_template(company_id: int):
    from fastapi.responses import Response
    companies.get_company(get_db(), company_id)  # raises 404 if missing
    data = import_excel_mod.build_template_bytes_company_scoped()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=activerse_import_template.xlsx"},
    )


@app.post("/companies/{company_id}/import/excel")
async def import_excel_for_company(company_id: int, file: UploadFile = File(...)):
    return import_excel_mod.import_excel_for_company(get_db(), company_id, file)


# ── Dashboard ─────────────────────────────────────────────────────────────

@app.get("/dashboard/health")
async def dash_health():
    return dashboard.get_health(get_db())


@app.get("/dashboard/leaderboard")
async def dash_leaderboard(
    game: str = Query(default="all"),
    period: str = Query(default="alltime"),
    limit: int = Query(default=20, le=100),
    board: str = Query(default="individual"),
    company_id: int | None = Query(default=None),
    group_id: int | None = Query(default=None),
    play_mode: str | None = Query(default=None),
    min_size: int | None = Query(default=None),
    max_size: int | None = Query(default=None),
    two_card: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    tournament_id: int | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    difficulty: str | None = Query(default=None),
):
    return dashboard.get_leaderboard(
        get_db(), game, period, limit, board, company_id, group_id,
        play_mode=play_mode, min_size=min_size, max_size=max_size, two_card=two_card,
        include_archived=include_archived,
        tournament_id=tournament_id, offset=offset, difficulty=difficulty,
    )


# ── Tournaments (P4a) ───────────────────────────────────────────────────

@app.get("/tournaments")
async def list_tournaments_route(
    scope: str | None = Query(default=None),
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
):
    return tournaments_mod.list_tournaments(
        get_db(), scope=scope, type=type, status=status, company_id=company_id
    )


@app.get("/tournaments/active")
async def tournaments_active():
    return tournaments_mod.get_active_globals(get_db())


@app.post("/tournaments")
async def create_tournament_route(body: TournamentCreate):
    return tournaments_mod.create_tournament(get_db(), body.model_dump())


@app.get("/tournaments/{tournament_id}")
async def get_tournament_route(tournament_id: int):
    return tournaments_mod.get_tournament(get_db(), tournament_id)


@app.put("/tournaments/{tournament_id}")
async def update_tournament_route(tournament_id: int, body: TournamentUpdate):
    return tournaments_mod.update_tournament(
        get_db(), tournament_id, body.model_dump(exclude_unset=True)
    )


@app.delete("/tournaments/{tournament_id}")
async def delete_tournament_route(tournament_id: int):
    return tournaments_mod.delete_tournament(get_db(), tournament_id)


@app.post("/tournaments/{tournament_id}/activate-global")
async def activate_global_route(tournament_id: int, body: ActivateGlobal = ActivateGlobal()):
    return tournaments_mod.activate_global(
        get_db(), tournament_id, body.which
    )


@app.get("/tournaments/{tournament_id}/leaderboard")
async def tournament_leaderboard_route(
    tournament_id: int,
    period: str = Query(default="alltime"),
    game: str = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    company_id: int | None = Query(default=None),
    group_id: int | None = Query(default=None),
    play_mode: str | None = Query(default=None),
    min_size: int | None = Query(default=None, ge=0),
    max_size: int | None = Query(default=None, ge=0),
    two_card: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    difficulty: str | None = Query(default=None),
):
    return tournaments_mod.get_tournament_leaderboard(
        get_db(), tournament_id,
        period=period, game=game, limit=limit, offset=offset,
        company_id=company_id, group_id=group_id, play_mode=play_mode,
        min_size=min_size, max_size=max_size, two_card=two_card,
        include_archived=include_archived, difficulty=difficulty,
    )


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
