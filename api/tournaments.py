"""Tournament CRUD and leaderboard envelope (P4a)."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import HTTPException

from .database import Database
from .leaderboard import (
    effective_window,
    resolve_tournament,
    tournament_leaderboard,
    tournament_leaderboard_count,
    _TYPE_TO_BOARD,
)
from . import dashboard

VALID_PLAY_MODES = frozenset({"quick_play", "team_battle", "tournament"})


def _now_iso(db: Database) -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_date_field(value: Optional[str], field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")
    return value


def _window_label(row: dict) -> str:
    s, e = row.get("starts_at"), row.get("ends_at")
    if not s and not e:
        return "All time"
    if s and e:
        return f"{s} – {e}"
    if s:
        return f"From {s}"
    return f"Until {e}"


def _active_global_ids(db: Database) -> tuple[Optional[int], Optional[int]]:
    settings = db.get_all_settings()
    solo_id = team_id = None
    for key, attr in (
        ("active_global_solo_tournament_id", "solo"),
        ("active_global_team_tournament_id", "team"),
    ):
        raw = settings.get(key)
        if raw:
            try:
                tid = int(raw)
                if attr == "solo":
                    solo_id = tid
                else:
                    team_id = tid
            except (TypeError, ValueError):
                pass
    return solo_id, team_id


def _serialize_tournament(db: Database, row: dict, *, counts: bool = False) -> dict:
    solo_active, team_active = _active_global_ids(db)
    out = dict(row)
    out["is_active_global"] = row["id"] in (solo_active, team_active)
    out["window_label"] = _window_label(row)
    if counts:
        board = _TYPE_TO_BOARD[row["type"]]
        out["play_count"] = tournament_leaderboard_count(
            db, board=board, tournament_id=row["id"], use_active=False
        )
        if row["type"] == "solo":
            ent = db._execute(
                "SELECT COUNT(DISTINCT cs.player_id) AS c FROM central_scores cs "
                "WHERE cs.player_id IS NOT NULL",
                fetch="one",
            )
        else:
            ent = db._execute(
                "SELECT COUNT(DISTINCT cts.group_id) AS c FROM central_team_scores cts "
                "WHERE cts.session_id IS NOT NULL AND cts.group_id IS NOT NULL",
                fetch="one",
            )
        out["entrant_count"] = int(ent["c"]) if ent else 0
    return out


def list_tournaments(
    db: Database,
    scope: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    company_id: Optional[int] = None,
):
    clauses = ["1=1"]
    params: list[Any] = []
    if scope is not None:
        clauses.append("scope = ?")
        params.append(scope)
    if type is not None:
        clauses.append("type = ?")
        params.append(type)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    if company_id is not None:
        clauses.append("company_id = ?")
        params.append(company_id)
    where = " AND ".join(clauses)
    rows = db._execute(
        f"SELECT * FROM tournaments WHERE {where} "
        "ORDER BY type, scope, starts_at DESC, id DESC",
        tuple(params),
        fetch="all",
    )
    return [_serialize_tournament(db, dict(r)) for r in (rows or [])]


def get_active_globals(db: Database):
    solo = resolve_tournament(db, None, "individual", use_active=True)
    team = resolve_tournament(db, None, "team", use_active=True)
    return {
        "solo": _serialize_tournament(db, solo) if solo else None,
        "team": _serialize_tournament(db, team) if team else None,
    }


def get_tournament(db: Database, tournament_id: int):
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    return _serialize_tournament(db, dict(row), counts=True)


def create_tournament(db: Database, body: dict):
    name = (body.get("name") or "").strip()
    if not name or len(name) > 80:
        raise HTTPException(422, "name must be non-empty and at most 80 characters")
    ttype = body.get("type")
    scope = body.get("scope")
    if ttype not in ("solo", "team"):
        raise HTTPException(422, "type must be solo or team")
    if scope not in ("global", "company"):
        raise HTTPException(422, "scope must be global or company")
    status = body.get("status") or "active"
    if status not in ("draft", "active", "archived"):
        raise HTTPException(422, "status must be draft, active, or archived")
    company_id = body.get("company_id")
    if scope == "global" and company_id is not None:
        raise HTTPException(422, "company_id must be null for global scope")
    if scope == "company":
        if company_id is None:
            raise HTTPException(422, "company_id required for company scope")
        if not db.get_company(company_id):
            raise HTTPException(404, "Company not found")
    starts_at = _parse_date_field(body.get("starts_at"), "starts_at")
    ends_at = _parse_date_field(body.get("ends_at"), "ends_at")
    if starts_at and ends_at and ends_at < starts_at:
        raise HTTPException(422, "ends_at must be on or after starts_at")
    created_by = body.get("created_by") or ""
    now = _now_iso(db)
    tid = db._executemany_return_id(
        "INSERT INTO tournaments "
        "(name, type, scope, company_id, starts_at, ends_at, status, created_at, updated_at, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (name, ttype, scope, company_id, starts_at, ends_at, status, now, now, created_by),
    )
    return get_tournament(db, tid)


def update_tournament(db: Database, tournament_id: int, body: dict):
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    row = dict(row)
    for imm in ("type", "scope", "company_id"):
        if imm in body and body[imm] != row[imm]:
            raise HTTPException(422, f"{imm} is immutable after create")
    if row.get("system_key"):
        for imm in ("starts_at", "ends_at", "type", "scope", "company_id"):
            if imm in body and body.get(imm) != row.get(imm):
                raise HTTPException(409, "System tournament window and type are immutable")
        solo_active, team_active = _active_global_ids(db)
        if row["id"] in (solo_active, team_active):
            new_status = body.get("status", row["status"])
            if new_status in ("draft", "archived"):
                raise HTTPException(
                    409, "Cannot archive or draft the active global tournament"
                )
    name = body.get("name")
    if name is not None:
        name = name.strip()
        if not name or len(name) > 80:
            raise HTTPException(422, "name must be non-empty and at most 80 characters")
    starts_at = body.get("starts_at", row["starts_at"])
    ends_at = body.get("ends_at", row["ends_at"])
    if "starts_at" in body:
        starts_at = _parse_date_field(body["starts_at"], "starts_at")
    if "ends_at" in body:
        ends_at = _parse_date_field(body["ends_at"], "ends_at")
    if starts_at and ends_at and ends_at < starts_at:
        raise HTTPException(422, "ends_at must be on or after starts_at")
    status = body.get("status", row["status"])
    if status not in ("draft", "active", "archived"):
        raise HTTPException(422, "status must be draft, active, or archived")
    now = _now_iso(db)
    db._execute(
        "UPDATE tournaments SET name=?, starts_at=?, ends_at=?, status=?, updated_at=? WHERE id=?",
        (
            name if name is not None else row["name"],
            starts_at,
            ends_at,
            status,
            now,
            tournament_id,
        ),
    )
    return get_tournament(db, tournament_id)


def delete_tournament(db: Database, tournament_id: int):
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    row = dict(row)
    if row.get("system_key"):
        raise HTTPException(409, "Cannot delete system tournament")
    solo_active, team_active = _active_global_ids(db)
    if row["id"] in (solo_active, team_active):
        raise HTTPException(409, "Activate another global tournament before delete")
    db._execute("DELETE FROM tournaments WHERE id = ?", (tournament_id,))
    return {"success": True}


def activate_global(db: Database, tournament_id: int, which: Optional[str] = None):
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    row = dict(row)
    if row["scope"] != "global":
        raise HTTPException(409, "Only global tournaments can be activated")
    if row["status"] != "active":
        raise HTTPException(409, "Tournament must be active")
    if which is not None and which != row["type"]:
        raise HTTPException(422, "which must match tournament type")
    key = (
        "active_global_solo_tournament_id"
        if row["type"] == "solo"
        else "active_global_team_tournament_id"
    )
    db.set_setting(key, str(tournament_id))
    solo_active, team_active = _active_global_ids(db)
    return {"success": True, "solo_id": solo_active, "team_id": team_active}


def get_tournament_leaderboard(
    db: Database,
    tournament_id: int,
    *,
    period: str = "alltime",
    game: str = "all",
    limit: int = 20,
    offset: int = 0,
    company_id: Optional[int] = None,
    group_id: Optional[int] = None,
    play_mode: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    two_card: Optional[bool] = None,
    include_archived: bool = False,
    difficulty: Optional[str] = None,
):
    if offset < 0:
        raise HTTPException(422, "offset must be >= 0")
    if limit < 1 or limit > 100:
        raise HTTPException(422, "limit must be between 1 and 100")
    if min_size is not None and min_size < 0:
        raise HTTPException(422, "min_size must be >= 0")
    if max_size is not None and max_size < 0:
        raise HTTPException(422, "max_size must be >= 0")
    if play_mode is not None and play_mode not in VALID_PLAY_MODES:
        raise HTTPException(422, "play_mode must be quick_play, team_battle, or tournament")

    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    trow = dict(row)
    board = _TYPE_TO_BOARD[trow["type"]]

    try:
        rows = tournament_leaderboard(
            db,
            board=board,
            tournament_id=tournament_id,
            use_active=False,
            period=period,
            game=game,
            limit=limit,
            offset=offset,
            company_id=company_id,
            group_id=group_id,
            play_mode=play_mode,
            min_size=min_size,
            max_size=max_size,
            two_card=two_card,
            include_archived=include_archived,
            difficulty=difficulty,
            add_rank=True,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if board == "team":
        rows = dashboard.enrich_team_rows(rows)

    total = tournament_leaderboard_count(
        db,
        board=board,
        tournament_id=tournament_id,
        use_active=False,
        period=period,
        game=game,
        company_id=company_id,
        group_id=group_id,
        play_mode=play_mode,
        min_size=min_size,
        max_size=max_size,
        two_card=two_card,
        include_archived=include_archived,
        difficulty=difficulty,
    )
    window = effective_window(
        db,
        board=board,
        tournament_id=tournament_id,
        use_active=False,
        period=period,
    )
    return {
        "tournament": {
            "id": trow["id"],
            "name": trow["name"],
            "type": trow["type"],
            "scope": trow["scope"],
            "starts_at": trow["starts_at"],
            "ends_at": trow["ends_at"],
        },
        "board": board,
        "filters": {
            "period": period,
            "game": game,
            "play_mode": play_mode,
            "min_size": min_size,
            "max_size": max_size,
            "two_card": two_card,
            "include_archived": include_archived,
            "difficulty": difficulty,
            "company_id": company_id,
            "group_id": group_id,
        },
        "window": window,
        "total": total,
        "limit": limit,
        "offset": offset,
        "rows": rows,
    }
