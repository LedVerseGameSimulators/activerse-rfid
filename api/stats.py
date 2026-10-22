"""Read-only stat sheet rollups (P5a)."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from .config import GAME_REGISTRY
from .database import Database
from .leaderboard import (
    _TYPE_TO_BOARD,
    _build,
    _merge_bounds,
    _tournament_window_bounds,
    effective_window,
    period_bounds,
    tournament_entrant_count,
    tournament_leaderboard,
    tournament_leaderboard_count,
)
from . import dashboard
from .sessions import _minutes_remaining

VALID_PLAY_MODES = frozenset({"quick_play", "team_battle", "tournament"})
_STRICT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_RECENT_PLAYS_LIMIT = 20
_LEDGER_EVENTS_LIMIT = 50
_TOP_LIST_LIMIT = 10
_TOURNAMENT_LIST_LIMIT = 20
_MEMBER_LIST_LIMIT = 100
_VISIT_SESSIONS_LIMIT = 20
_PER_DAY_LIMIT = 30


def _parse_date_field(value: Optional[str], field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not _STRICT_DATE_RE.match(value):
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(422, f"{field} must be YYYY-MM-DD")


def _check_play_mode(play_mode: Optional[str]) -> None:
    if play_mode is not None and play_mode not in VALID_PLAY_MODES:
        raise HTTPException(422, "play_mode must be quick_play, team_battle, or tournament")


def _resolve_play_window(
    period: str,
    date_from: Optional[str],
    date_to: Optional[str],
    today: Optional[date] = None,
) -> tuple[Optional[str], Optional[str], bool]:
    today = today or date.today()
    p_lo, p_hi = period_bounds(period, today)
    d_lo = date_from
    d_hi = None
    if date_to:
        d_hi = (date.fromisoformat(date_to) + timedelta(days=1)).isoformat()
    lo, hi, vacuous = _merge_bounds(p_lo, p_hi, d_lo, d_hi)
    return lo, hi, vacuous


def _roster_n_solo() -> str:
    return "MAX(COALESCE(cs.roster_size_at_play, t.member_count, 1), 1)"


def _roster_n_team() -> str:
    return "MAX(COALESCE(cts.roster_size_at_play, cts.member_count, 1), 1)"


def _append_played_window(
    clauses: list[str],
    params: list[Any],
    col: str,
    lo: Optional[str],
    hi: Optional[str],
) -> None:
    if lo is not None:
        clauses.append(f"{col} >= ?")
        params.append(lo)
    if hi is not None:
        clauses.append(f"{col} < ?")
        params.append(hi)


def _solo_score_where(
    *,
    lo: Optional[str],
    hi: Optional[str],
    game: str,
    play_mode: Optional[str],
    include_archived: bool,
    min_size: Optional[int],
    max_size: Optional[int],
    player_id: Optional[int] = None,
    group_id: Optional[int] = None,
    company_id: Optional[int] = None,
    session_id: Optional[int] = None,
) -> tuple[str, list[Any]]:
    clauses = ["cs.player_id IS NOT NULL"]
    params: list[Any] = []
    from_sql = (
        "FROM central_scores cs "
        "LEFT JOIN groups g ON g.id = cs.group_id "
        "LEFT JOIN central_team_scores t ON t.id = cs.team_score_id "
    )
    if not include_archived:
        clauses.append("(cs.group_id IS NULL OR g.archived_at IS NULL)")
    if player_id is not None:
        clauses.append("cs.player_id = ?")
        params.append(player_id)
    if group_id is not None:
        clauses.append("cs.group_id = ?")
        params.append(group_id)
    if company_id is not None:
        clauses.append("cs.company_id = ?")
        params.append(company_id)
    if session_id is not None:
        clauses.append("cs.session_id = ?")
        params.append(session_id)
    if game != "all":
        clauses.append("cs.game = ?")
        params.append(game)
    _append_played_window(clauses, params, "cs.played_at", lo, hi)
    if play_mode is not None:
        clauses.append("cs.play_mode = ?")
        params.append(play_mode)
    roster_n = _roster_n_solo()
    if min_size is not None:
        clauses.append(f"{roster_n} >= ?")
        params.append(max(int(min_size), 0))
    if max_size is not None:
        clauses.append(f"{roster_n} <= ?")
        params.append(max(int(max_size), 0))
    return f"{from_sql} WHERE {' AND '.join(clauses)}", params


def _team_score_where(
    *,
    lo: Optional[str],
    hi: Optional[str],
    game: str,
    play_mode: Optional[str],
    include_archived: bool,
    min_size: Optional[int],
    max_size: Optional[int],
    group_id: Optional[int] = None,
    company_id: Optional[int] = None,
    session_id: Optional[int] = None,
    require_attribution: bool = True,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    if require_attribution:
        clauses.extend(["cts.session_id IS NOT NULL", "cts.group_id IS NOT NULL"])
    params: list[Any] = []
    from_sql = (
        "FROM central_team_scores cts "
        "LEFT JOIN groups g ON g.id = cts.group_id "
    )
    if not include_archived:
        clauses.append("(cts.group_id IS NULL OR g.archived_at IS NULL)")
    if group_id is not None:
        clauses.append("cts.group_id = ?")
        params.append(group_id)
    if company_id is not None:
        clauses.append("cts.company_id = ?")
        params.append(company_id)
    if session_id is not None:
        clauses.append("cts.session_id = ?")
        params.append(session_id)
    if game != "all":
        clauses.append("cts.game = ?")
        params.append(game)
    _append_played_window(clauses, params, "cts.played_at", lo, hi)
    if play_mode is not None:
        clauses.append("cts.play_mode = ?")
        params.append(play_mode)
    roster_n = _roster_n_team()
    if min_size is not None:
        clauses.append(f"{roster_n} >= ?")
        params.append(max(int(min_size), 0))
    if max_size is not None:
        clauses.append(f"{roster_n} <= ?")
        params.append(max(int(max_size), 0))
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return f"{from_sql}{where_sql}", params


def _play_time_totals(
    db: Database,
    *,
    player_id: Optional[int] = None,
    group_id: Optional[int] = None,
    company_id: Optional[int] = None,
    lo: Optional[str] = None,
    hi: Optional[str] = None,
) -> dict:
    clauses: list[str] = []
    params: list[Any] = []
    if player_id is not None:
        clauses.append("player_id = ?")
        params.append(player_id)
    if group_id is not None:
        clauses.append("group_id = ?")
        params.append(group_id)
    if company_id is not None:
        clauses.append("company_id = ?")
        params.append(company_id)
    if lo is not None:
        clauses.append("earned_at >= ?")
        params.append(lo)
    if hi is not None:
        clauses.append("earned_at < ?")
        params.append(hi)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db._execute(
        f"SELECT source, SUM(minutes) AS total FROM play_time_events{where} "
        "GROUP BY source",
        tuple(params),
        fetch="all",
    )
    by_source = {r["source"]: float(r["total"] or 0) for r in (rows or [])}
    earned = by_source.get("visit_start", 0) + by_source.get("roster_join", 0)
    return {
        "earned_min": round(earned, 2),
        "adjust_net_min": round(by_source.get("adjust", 0), 2),
        "refund_min": round(by_source.get("refund", 0), 2),
    }


def _session_status(session: dict) -> str:
    if session.get("closed_at"):
        return "closed"
    try:
        expiry = datetime.strptime(session["expiry_at"], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return "open"
    if expiry <= datetime.now():
        return "expired"
    return "open"


def _head_to_head_record(db: Database, tfw: str, params: list) -> dict:
    """W/L/draw from Team Battle rows linked by match_key."""
    from_joined = tfw.replace(
        "FROM central_team_scores cts",
        "FROM central_team_scores cts "
        "JOIN central_team_scores opp ON opp.match_key = cts.match_key "
        "AND opp.id != cts.id AND opp.group_id != cts.group_id",
        1,
    )
    q = (
        "SELECT cts.match_key, cts.score AS our_score, opp.score AS opp_score "
        f"{from_joined} AND cts.match_key IS NOT NULL"
    )
    rows = db._execute(q, tuple(params), fetch="all")
    wins = losses = draws = 0
    seen: set[str] = set()
    for r in rows or []:
        mk = r["match_key"]
        if mk in seen:
            continue
        seen.add(mk)
        ours = float(r["our_score"] or 0)
        theirs = float(r["opp_score"] or 0)
        if ours > theirs:
            wins += 1
        elif ours < theirs:
            losses += 1
        else:
            draws += 1
    return {"wins": wins, "losses": losses, "draws": draws}


def get_player_stats(
    db: Database,
    player_id: int,
    *,
    period: str = "alltime",
    game: str = "all",
    play_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archived: bool = False,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    today: Optional[date] = None,
):
    _check_play_mode(play_mode)
    d_from = _parse_date_field(date_from, "date_from")
    d_to = _parse_date_field(date_to, "date_to")
    lo, hi, vacuous = _resolve_play_window(period, d_from, d_to, today=today)

    player_rows = db.search_custom_tb_by_id(player_id)
    if not player_rows:
        raise HTTPException(404, "Player not found")
    player_row = player_rows[0]
    membership = db.get_company_membership(player_id)
    solo_gid = db.get_solo_group_id(player_id)
    groups_raw = db.list_groups_for_player(player_id, include_archived=True)
    groups = [
        {
            "id": g["id"],
            "name": g["name"],
            "kind": g.get("kind") or "team",
            "archived": g.get("archived_at") is not None,
        }
        for g in groups_raw
    ]
    company_block = None
    if membership:
        company_block = {"id": membership["company_id"], "name": membership["company_name"]}

    fw, params = _solo_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        player_id=player_id,
    )
    if vacuous:
        play_agg = None
    else:
        play_agg = db._execute(
            f"SELECT COUNT(*) AS cnt, MAX(cs.score) AS best, AVG(cs.score) AS avg, "
            f"SUM(cs.score) AS total, MIN(cs.played_at) AS first_played_at, "
            f"MAX(cs.played_at) AS last_played_at {fw}",
            tuple(params),
            fetch="one",
        )

    def _grouped(sql_suffix: str, extra_params: tuple = ()) -> list:
        if vacuous:
            return []
        rows = db._execute(
            f"SELECT {sql_suffix} {fw} GROUP BY 1 ORDER BY 1",
            tuple(params) + extra_params,
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    by_game = []
    if not vacuous:
        rows = db._execute(
            f"SELECT cs.game AS game, COUNT(*) AS plays, MAX(cs.score) AS best, "
            f"AVG(cs.score) AS avg {fw} GROUP BY cs.game ORDER BY plays DESC",
            tuple(params),
            fetch="all",
        )
        by_game = [
            {
                "game": r["game"],
                "plays": int(r["plays"]),
                "best": float(r["best"] or 0),
                "avg": round(float(r["avg"] or 0), 2),
            }
            for r in (rows or [])
        ]

    by_mode = []
    if not vacuous:
        rows = db._execute(
            f"SELECT cs.play_mode AS play_mode, COUNT(*) AS plays {fw} "
            "GROUP BY cs.play_mode ORDER BY plays DESC",
            tuple(params),
            fetch="all",
        )
        by_mode = [
            {"play_mode": r["play_mode"], "plays": int(r["plays"])} for r in (rows or [])
        ]

    by_size = []
    if not vacuous:
        n_expr = _roster_n_solo()
        rows = db._execute(
            f"SELECT {n_expr} AS n, COUNT(*) AS plays {fw} GROUP BY n ORDER BY n",
            tuple(params),
            fetch="all",
        )
        by_size = [{"n": int(r["n"]), "plays": int(r["plays"])} for r in (rows or [])]

    pt = _play_time_totals(db, player_id=player_id, lo=lo, hi=hi)
    ledger_rows = db._execute(
        "SELECT earned_at, source, minutes, session_id FROM play_time_events "
        "WHERE player_id = ? ORDER BY earned_at DESC LIMIT ?",
        (player_id, _LEDGER_EVENTS_LIMIT),
        fetch="all",
    )
    pt["events"] = [
        {
            "earned_at": r["earned_at"],
            "source": r["source"],
            "minutes": float(r["minutes"]),
            "session_id": r["session_id"],
        }
        for r in (ledger_rows or [])
    ]

    led = db._execute(
        "SELECT COUNT(*) AS c FROM player_sessions WHERE player_id = ?",
        (player_id,),
        fetch="one",
    )
    roster_visits = db._execute(
        "SELECT COUNT(DISTINCT session_id) AS c FROM session_roster WHERE player_id = ?",
        (player_id,),
        fetch="one",
    )
    last_visit = db._execute(
        "SELECT MAX(ps.issued_at) AS last_visit_at FROM session_roster sr "
        "JOIN player_sessions ps ON ps.id = sr.session_id WHERE sr.player_id = ?",
        (player_id,),
        fetch="one",
    )

    tournaments_out: list[dict] = []
    t_rows = db._execute(
        "SELECT * FROM tournaments WHERE type = 'solo' AND status != 'archived' "
        "ORDER BY starts_at DESC, id DESC LIMIT ?",
        (_TOURNAMENT_LIST_LIMIT,),
        fetch="all",
    )
    for t in t_rows or []:
        tdict = dict(t)
        t_lo, t_hi = _tournament_window_bounds(tdict)
        w_lo, w_hi, w_vac = _merge_bounds(lo, hi, t_lo, t_hi)
        if w_vac:
            continue
        tfw, tparams = _solo_score_where(
            lo=w_lo,
            hi=w_hi,
            game=game,
            play_mode=play_mode,
            include_archived=False,
            min_size=min_size,
            max_size=max_size,
            player_id=player_id,
        )
        if tdict.get("scope") == "company":
            tfw = tfw.replace(
                "WHERE",
                "WHERE cs.company_id = ? AND",
                1,
            )
            tparams = [tdict["company_id"]] + tparams
        agg = db._execute(
            f"SELECT COUNT(*) AS plays, MAX(cs.score) AS best {tfw}",
            tuple(tparams),
            fetch="one",
        )
        plays_n = int(agg["plays"] or 0) if agg else 0
        if plays_n == 0:
            continue
        best = float(agg["best"] or 0)
        rank_row = db._execute(
            f"SELECT COUNT(*) AS c {tfw} AND cs.score > ?",
            tuple(tparams) + (best,),
            fetch="one",
        )
        best_rank = 1 + int(rank_row["c"] or 0) if rank_row else 1
        tournaments_out.append({
            "id": tdict["id"],
            "name": tdict["name"],
            "plays": plays_n,
            "best": best,
            "best_rank": best_rank,
        })

    recent = []
    if not vacuous:
        rows = db._execute(
            f"SELECT cs.*, g.name AS group_name {fw} "
            "ORDER BY cs.played_at DESC, cs.id DESC LIMIT ?",
            tuple(params) + (_RECENT_PLAYS_LIMIT,),
            fetch="all",
        )
        recent = [dict(r) for r in rows] if rows else []

    plays_block = {
        "count": 0,
        "best": 0.0,
        "avg": 0.0,
        "total": 0.0,
        "first_played_at": None,
        "last_played_at": None,
        "by_game": by_game,
        "by_mode": by_mode,
        "by_size": by_size,
    }
    if play_agg and not vacuous:
        plays_block = {
            "count": int(play_agg["cnt"] or 0),
            "best": float(play_agg["best"] or 0),
            "avg": round(float(play_agg["avg"] or 0), 2),
            "total": round(float(play_agg["total"] or 0), 2),
            "first_played_at": play_agg["first_played_at"],
            "last_played_at": play_agg["last_played_at"],
            "by_game": by_game,
            "by_mode": by_mode,
            "by_size": by_size,
        }

    return {
        "player": {
            "id": player_id,
            "name": player_row.get("name"),
            "company": company_block,
            "solo_group_id": solo_gid,
            "groups": groups,
        },
        "play_time": pt,
        "visits": {
            "led": int(led["c"] or 0) if led else 0,
            "on_roster": int(roster_visits["c"] or 0) if roster_visits else 0,
            "last_visit_at": last_visit["last_visit_at"] if last_visit else None,
        },
        "plays": plays_block,
        "tournaments": tournaments_out,
        "recent_plays": recent,
        "filters": {
            "period": period,
            "game": game,
            "play_mode": play_mode,
            "date_from": d_from,
            "date_to": d_to,
            "include_archived": include_archived,
            "min_size": min_size,
            "max_size": max_size,
        },
        "window": {"from": lo, "to_exclusive": hi},
    }


def get_session_stats(db: Database, session_id: int):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    payer = db.search_custom_tb_by_id(session["player_id"])
    payer_name = payer[0]["name"] if payer else None
    group_name = None
    company_name = None
    if session.get("group_id"):
        grp = db.get_group(session["group_id"])
        if grp:
            group_name = grp.get("name")
    if session.get("company_id"):
        co = db.get_company(session["company_id"])
        if co:
            company_name = co.get("name")

    roster_members = db.get_session_roster(session_id)
    roster_out = []
    for m in roster_members:
        pte = db._execute(
            "SELECT earned_at, source, minutes FROM play_time_events "
            "WHERE session_id = ? AND player_id = ? AND source IN ('visit_start', 'roster_join') "
            "ORDER BY earned_at LIMIT 1",
            (session_id, m["player_id"]),
            fetch="one",
        )
        earned_row = db._execute(
            "SELECT SUM(minutes) AS m FROM play_time_events "
            "WHERE session_id = ? AND player_id = ? AND source IN ('visit_start', 'roster_join')",
            (session_id, m["player_id"]),
            fetch="one",
        )
        roster_out.append({
            "player_id": m["player_id"],
            "name": m["name"],
            "is_payer": bool(m.get("is_payer")),
            "joined_at": pte["earned_at"] if pte else session.get("issued_at"),
            "joined_via": pte["source"] if pte else "visit_start",
            "earned_min": round(float(earned_row["m"] or 0), 2) if earned_row else 0.0,
        })

    adjustments = db._execute(
        "SELECT id, adjusted_at, delta_min, adjustment_mode, balance_delta_min, "
        "reason, adjusted_by FROM session_adjustments WHERE session_id = ? "
        "ORDER BY adjusted_at",
        (session_id,),
        fetch="all",
    )
    ledger = db._execute(
        "SELECT earned_at, player_id, source, minutes FROM play_time_events "
        "WHERE session_id = ? ORDER BY earned_at",
        (session_id,),
        fetch="all",
    )

    team_rows = db._execute(
        "SELECT id AS team_score_id, game, play_mode, roster_size_at_play, score, "
        "played_at, two_card_play, match_key FROM central_team_scores "
        "WHERE session_id = ? ORDER BY played_at, id",
        (session_id,),
        fetch="all",
    )
    play_rows = [dict(r) for r in team_rows] if team_rows else []
    agg = db._execute(
        "SELECT COUNT(*) AS cnt, MAX(score) AS best, SUM(score) AS total "
        "FROM central_team_scores WHERE session_id = ?",
        (session_id,),
        fetch="one",
    )
    by_member_rows = db._execute(
        "SELECT cs.player_id, ci.name, COUNT(*) AS plays, SUM(cs.score) AS total_share, "
        "MAX(cs.score) AS best_share FROM central_scores cs "
        "JOIN custom_info ci ON ci.custom_id = cs.player_id "
        "WHERE cs.session_id = ? AND cs.player_id IS NOT NULL GROUP BY cs.player_id",
        (session_id,),
        fetch="all",
    )
    by_member = [
        {
            "player_id": r["player_id"],
            "name": r["name"],
            "plays": int(r["plays"]),
            "total_share": round(float(r["total_share"] or 0), 2),
            "best_share": float(r["best_share"] or 0),
        }
        for r in (by_member_rows or [])
    ]

    return {
        "session": {
            "id": session_id,
            "player_id": session["player_id"],
            "payer_name": payer_name,
            "card_id": session.get("card_id"),
            "issued_at": session.get("issued_at"),
            "expiry_at": session.get("expiry_at"),
            "closed_at": session.get("closed_at"),
            "duration_min": session.get("duration_min"),
            "status": _session_status(session),
            "group_id": session.get("group_id"),
            "group_name": group_name,
            "company_id": session.get("company_id"),
            "company_name": company_name,
            "minutes_remaining": _minutes_remaining(session["expiry_at"]),
        },
        "roster": roster_out,
        "adjustments": [
            {
                "id": a["id"],
                "adjusted_at": a["adjusted_at"],
                "delta_min": a["delta_min"],
                "adjustment_mode": (dict(a).get("adjustment_mode") or "free_clock"),
                "balance_delta_min": float(dict(a).get("balance_delta_min") or 0),
                "reason": dict(a).get("reason") or "",
                "adjusted_by": dict(a).get("adjusted_by") or "",
            }
            for a in (adjustments or [])
        ],
        "ledger": [
            {
                "earned_at": r["earned_at"],
                "player_id": r["player_id"],
                "source": r["source"],
                "minutes": float(r["minutes"]),
            }
            for r in (ledger or [])
        ],
        "plays": {
            "count": int(agg["cnt"] or 0) if agg else 0,
            "best_team_score": float(agg["best"] or 0) if agg else 0.0,
            "total_team_score": round(float(agg["total"] or 0), 2) if agg else 0.0,
            "rows": play_rows,
            "by_member": by_member,
        },
    }


def get_group_stats(
    db: Database,
    group_id: int,
    *,
    period: str = "alltime",
    game: str = "all",
    play_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archived: bool = True,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    today: Optional[date] = None,
):
    _check_play_mode(play_mode)
    d_from = _parse_date_field(date_from, "date_from")
    d_to = _parse_date_field(date_to, "date_to")
    lo, hi, vacuous = _resolve_play_window(period, d_from, d_to, today=today)

    grp = db.get_group(group_id)
    if not grp:
        raise HTTPException(404, "Group not found")

    members_raw = db.get_group_members(group_id)
    members = [
        {
            "player_id": m["player_id"],
            "name": m["name"],
            "is_leader": m["player_id"] == grp.get("leader_player_id"),
        }
        for m in members_raw
    ]

    tfw, tparams = _team_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        group_id=group_id,
    )
    team_agg = None if vacuous else db._execute(
        f"SELECT COUNT(*) AS cnt, MAX(cts.score) AS best, AVG(cts.score) AS avg {tfw}",
        tuple(tparams),
        fetch="one",
    )
    match_row = None if vacuous else db._execute(
        f"SELECT COUNT(DISTINCT cts.match_key) AS matches {tfw} AND cts.match_key IS NOT NULL",
        tuple(tparams),
        fetch="one",
    )
    h2h = {"wins": 0, "losses": 0, "draws": 0}
    if not vacuous:
        h2h = _head_to_head_record(db, tfw, tparams)

    sfw, sparams = _solo_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        group_id=group_id,
    )
    sfw_ci = sfw.replace(
        "FROM central_scores cs",
        "FROM central_scores cs JOIN custom_info ci ON ci.custom_id = cs.player_id",
        1,
    )
    share_rows = [] if vacuous else db._execute(
        f"SELECT cs.player_id, ci.name, COUNT(*) AS plays, MAX(cs.score) AS best_share, "
        f"SUM(cs.score) AS total_share {sfw_ci} "
        "GROUP BY cs.player_id ORDER BY total_share DESC",
        tuple(sparams),
        fetch="all",
    )
    member_shares = [
        {
            "player_id": r["player_id"],
            "name": r["name"],
            "plays": int(r["plays"]),
            "best_share": float(r["best_share"] or 0),
            "total_share": round(float(r["total_share"] or 0), 2),
        }
        for r in (share_rows or [])
    ]

    visit_rows = db._execute(
        "SELECT ps.id, ps.issued_at, ps.closed_at, ci.name AS payer "
        "FROM player_sessions ps "
        "JOIN custom_info ci ON ci.custom_id = ps.player_id "
        "WHERE ps.group_id = ? ORDER BY ps.issued_at DESC LIMIT ?",
        (group_id, _VISIT_SESSIONS_LIMIT),
        fetch="all",
    )
    visit_count = db._execute(
        "SELECT COUNT(*) AS c, MAX(issued_at) AS last, SUM(duration_min) AS dur "
        "FROM player_sessions WHERE group_id = ?",
        (group_id,),
        fetch="one",
    )

    pt = _play_time_totals(db, group_id=group_id, lo=lo, hi=hi)
    by_player_rows = db._execute(
        "SELECT player_id, SUM(minutes) AS earned FROM play_time_events "
        "WHERE group_id = ? AND source IN ('visit_start', 'roster_join') "
        "GROUP BY player_id ORDER BY earned DESC LIMIT ?",
        (group_id, _MEMBER_LIST_LIMIT),
        fetch="all",
    )
    pt["by_player"] = [
        {
            "player_id": r["player_id"],
            "earned_min": round(float(r["earned"] or 0), 2),
        }
        for r in (by_player_rows or [])
    ]

    tournaments_out: list[dict] = []
    t_rows = db._execute(
        "SELECT * FROM tournaments WHERE type = 'team' AND status != 'archived' "
        "ORDER BY starts_at DESC, id DESC LIMIT ?",
        (_TOURNAMENT_LIST_LIMIT,),
        fetch="all",
    )
    for t in t_rows or []:
        tdict = dict(t)
        t_lo, t_hi = _tournament_window_bounds(tdict)
        w_lo, w_hi, w_vac = _merge_bounds(lo, hi, t_lo, t_hi)
        if w_vac:
            continue
        gfw, gparams = _team_score_where(
            lo=w_lo,
            hi=w_hi,
            game=game,
            play_mode=play_mode,
            include_archived=False,
            min_size=min_size,
            max_size=max_size,
            group_id=group_id,
        )
        if tdict.get("scope") == "company":
            gfw = gfw.replace("WHERE", "WHERE cts.company_id = ? AND", 1)
            gparams = [tdict["company_id"]] + gparams
        agg = db._execute(
            f"SELECT COUNT(*) AS plays, MAX(cts.score) AS best {gfw}",
            tuple(gparams),
            fetch="one",
        )
        plays_n = int(agg["plays"] or 0) if agg else 0
        if plays_n == 0:
            continue
        best = float(agg["best"] or 0)
        rank_row = db._execute(
            f"SELECT COUNT(*) AS c {gfw} AND cts.score > ?",
            tuple(gparams) + (best,),
            fetch="one",
        )
        tournaments_out.append({
            "id": tdict["id"],
            "name": tdict["name"],
            "plays": plays_n,
            "best": best,
            "best_rank": 1 + int(rank_row["c"] or 0) if rank_row else 1,
        })

    def _team_breakdown(sql_group: str) -> list:
        if vacuous:
            return []
        rows = db._execute(
            f"SELECT {sql_group} {tfw} GROUP BY 1 ORDER BY 1",
            tuple(tparams),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    by_game = []
    if not vacuous:
        for r in db._execute(
            f"SELECT cts.game AS game, COUNT(*) AS plays, MAX(cts.score) AS best {tfw} "
            "GROUP BY cts.game ORDER BY plays DESC",
            tuple(tparams),
            fetch="all",
        ) or []:
            by_game.append({
                "game": r["game"],
                "plays": int(r["plays"]),
                "best": float(r["best"] or 0),
            })

    return {
        "group": {
            "id": group_id,
            "name": grp["name"],
            "kind": grp.get("kind") or "team",
            "company_id": grp.get("company_id"),
            "company_name": grp.get("company_name"),
            "leader_player_id": grp.get("leader_player_id"),
            "archived_at": grp.get("archived_at"),
        },
        "members": members,
        "visits": {
            "count": int(visit_count["c"] or 0) if visit_count else 0,
            "last_visit_at": visit_count["last"] if visit_count else None,
            "total_duration_min": int(visit_count["dur"] or 0) if visit_count else 0,
            "sessions": [
                {
                    "id": v["id"],
                    "issued_at": v["issued_at"],
                    "closed_at": v["closed_at"],
                    "payer": v["payer"],
                }
                for v in (visit_rows or [])
            ],
        },
        "team_plays": {
            "count": int(team_agg["cnt"] or 0) if team_agg else 0,
            "best": float(team_agg["best"] or 0) if team_agg else 0.0,
            "avg": round(float(team_agg["avg"] or 0), 2) if team_agg else 0.0,
            "by_game": by_game,
            "by_mode": [
                {"play_mode": r["play_mode"], "plays": int(r["plays"])}
                for r in _team_breakdown("cts.play_mode AS play_mode, COUNT(*) AS plays")
            ],
            "by_size": [
                {"n": int(r["n"]), "plays": int(r["plays"])}
                for r in (
                    db._execute(
                        f"SELECT {_roster_n_team()} AS n, COUNT(*) AS plays {tfw} GROUP BY n",
                        tuple(tparams),
                        fetch="all",
                    )
                    if not vacuous
                    else []
                )
            ],
            "matches": int(match_row["matches"] or 0) if match_row else 0,
            "head_to_head": h2h,
        },
        "member_shares": member_shares,
        "play_time": pt,
        "tournaments": tournaments_out,
        "filters": {
            "period": period,
            "game": game,
            "play_mode": play_mode,
            "date_from": d_from,
            "date_to": d_to,
            "include_archived": include_archived,
        },
        "window": {"from": lo, "to_exclusive": hi},
    }


def get_company_stats(
    db: Database,
    company_id: int,
    *,
    period: str = "alltime",
    game: str = "all",
    play_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archived: bool = False,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    today: Optional[date] = None,
):
    _check_play_mode(play_mode)
    d_from = _parse_date_field(date_from, "date_from")
    d_to = _parse_date_field(date_to, "date_to")
    lo, hi, vacuous = _resolve_play_window(period, d_from, d_to, today=today)

    co = db.get_company(company_id)
    if not co:
        raise HTTPException(404, "Company not found")

    members_list = db.list_company_members(company_id)
    players = [
        {"player_id": m["player_id"], "name": m["name"]}
        for m in members_list[:_MEMBER_LIST_LIMIT]
    ]

    all_groups = db.list_groups(company_id=company_id, include_archived=True)
    active_g = sum(1 for g in all_groups if not g.get("archived_at"))
    archived_g = sum(1 for g in all_groups if g.get("archived_at"))
    group_list = [
        {
            "id": g["id"],
            "name": g["name"],
            "kind": g.get("kind") or "team",
            "archived": g.get("archived_at") is not None,
            "member_count": int(g.get("member_count") or 0),
        }
        for g in all_groups[:_MEMBER_LIST_LIMIT]
    ]

    tfw, tparams = _team_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        company_id=company_id,
    )
    sfw, sparams = _solo_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        company_id=company_id,
    )

    team_plays = shares = unique_players = 0
    best_team = best_share = 0.0
    if not vacuous:
        t_agg = db._execute(f"SELECT COUNT(*) AS c, MAX(cts.score) AS best {tfw}", tuple(tparams), fetch="one")
        s_agg = db._execute(
            f"SELECT COUNT(*) AS c, MAX(cs.score) AS best, COUNT(DISTINCT cs.player_id) AS u {sfw}",
            tuple(sparams),
            fetch="one",
        )
        team_plays = int(t_agg["c"] or 0) if t_agg else 0
        shares = int(s_agg["c"] or 0) if s_agg else 0
        unique_players = int(s_agg["u"] or 0) if s_agg else 0
        best_team = float(t_agg["best"] or 0) if t_agg else 0.0
        best_share = float(s_agg["best"] or 0) if s_agg else 0.0

    pt = _play_time_totals(db, company_id=company_id, lo=lo, hi=hi)
    visits = db._execute(
        "SELECT COUNT(*) AS c FROM player_sessions WHERE company_id = ?",
        (company_id,),
        fetch="one",
    )

    top_players = []
    top_groups = []
    if not vacuous:
        sfw_ci = sfw.replace(
            "FROM central_scores cs",
            "FROM central_scores cs JOIN custom_info ci ON ci.custom_id = cs.player_id",
            1,
        )
        tp = db._execute(
            f"SELECT cs.player_id, ci.name, MAX(cs.score) AS best_share, COUNT(*) AS plays {sfw_ci} "
            "GROUP BY cs.player_id ORDER BY best_share DESC, plays DESC LIMIT ?",
            tuple(sparams) + (_TOP_LIST_LIMIT,),
            fetch="all",
        )
        top_players = [
            {
                "player_id": r["player_id"],
                "name": r["name"],
                "best_share": float(r["best_share"] or 0),
                "plays": int(r["plays"]),
            }
            for r in (tp or [])
        ]
        tfw_g = tfw.replace(
            "LEFT JOIN groups g ON g.id = cts.group_id",
            "JOIN groups g ON g.id = cts.group_id",
            1,
        )
        tg = db._execute(
            f"SELECT cts.group_id, g.name, MAX(cts.score) AS best, COUNT(*) AS plays {tfw_g} "
            "GROUP BY cts.group_id ORDER BY best DESC LIMIT ?",
            tuple(tparams) + (_TOP_LIST_LIMIT,),
            fetch="all",
        )
        top_groups = [
            {
                "group_id": r["group_id"],
                "name": r["name"],
                "best": float(r["best"] or 0),
                "plays": int(r["plays"]),
            }
            for r in (tg or [])
        ]

    tournaments_out = []
    t_rows = db._execute(
        "SELECT * FROM tournaments WHERE scope = 'company' AND company_id = ? "
        "AND status != 'archived' ORDER BY starts_at DESC LIMIT ?",
        (company_id, _TOURNAMENT_LIST_LIMIT),
        fetch="all",
    )
    for t in t_rows or []:
        tdict = dict(t)
        board = _TYPE_TO_BOARD[tdict["type"]]
        t_lo, t_hi = _tournament_window_bounds(tdict)
        w_lo, w_hi, w_vac = _merge_bounds(lo, hi, t_lo, t_hi)
        if w_vac:
            continue
        if board == "team":
            qfw, qparams = _team_score_where(
                lo=w_lo, hi=w_hi, game=game, play_mode=play_mode,
                include_archived=False, min_size=min_size, max_size=max_size,
                company_id=company_id,
            )
            cnt = db._execute(f"SELECT COUNT(*) AS c {qfw}", tuple(qparams), fetch="one")
        else:
            qfw, qparams = _solo_score_where(
                lo=w_lo, hi=w_hi, game=game, play_mode=play_mode,
                include_archived=False, min_size=min_size, max_size=max_size,
                company_id=company_id,
            )
            cnt = db._execute(f"SELECT COUNT(*) AS c {qfw}", tuple(qparams), fetch="one")
        plays_n = int(cnt["c"] or 0) if cnt else 0
        if plays_n:
            tournaments_out.append({
                "id": tdict["id"],
                "name": tdict["name"],
                "type": tdict["type"],
                "plays": plays_n,
            })

    plays_by_game = []
    plays_by_mode = []
    if not vacuous:
        team_by_game = {
            r["game"]: int(r["plays"])
            for r in db._execute(
                f"SELECT cts.game AS game, COUNT(*) AS plays {tfw} GROUP BY cts.game",
                tuple(tparams),
                fetch="all",
            ) or []
        }
        share_by_game = {
            r["game"]: int(r["plays"])
            for r in db._execute(
                f"SELECT cs.game AS game, COUNT(*) AS plays {sfw} GROUP BY cs.game",
                tuple(sparams),
                fetch="all",
            ) or []
        }
        for g in sorted(set(team_by_game) | set(share_by_game)):
            plays_by_game.append({
                "game": g,
                "team_plays": team_by_game.get(g, 0),
                "shares": share_by_game.get(g, 0),
            })
        plays_by_mode = [
            {"play_mode": r["play_mode"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT cts.play_mode AS play_mode, COUNT(*) AS plays {tfw} GROUP BY cts.play_mode",
                tuple(tparams),
                fetch="all",
            ) or []
        ]

    return {
        "company": {"id": company_id, "name": co["name"], "notes": co.get("notes") or ""},
        "members": {"count": len(members_list), "players": players},
        "groups": {
            "active": active_g,
            "archived": archived_g,
            "list": group_list,
        },
        "plays": {
            "team_plays": team_plays,
            "shares": shares,
            "unique_players": unique_players,
            "best_team_score": best_team,
            "best_share": best_share,
            "by_game": plays_by_game,
            "by_mode": plays_by_mode,
        },
        "play_time": pt,
        "visits": {"count": int(visits["c"] or 0) if visits else 0},
        "top_players": top_players,
        "top_groups": top_groups,
        "tournaments": tournaments_out,
        "window": {"from": lo, "to_exclusive": hi},
    }


def get_game_stats(
    db: Database,
    game_key: str,
    *,
    period: str = "alltime",
    play_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archived: bool = False,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    today: Optional[date] = None,
):
    if game_key not in GAME_REGISTRY:
        raise HTTPException(404, "Unknown game")
    _check_play_mode(play_mode)
    d_from = _parse_date_field(date_from, "date_from")
    d_to = _parse_date_field(date_to, "date_to")
    lo, hi, vacuous = _resolve_play_window(period, d_from, d_to, today=today)

    health_row = db._execute(
        "SELECT status, last_checked FROM game_health WHERE game = ?",
        (game_key,),
        fetch="one",
    )
    health = {
        "status": health_row["status"] if health_row else "unknown",
        "last_checked": health_row["last_checked"] if health_row else None,
    }

    tfw, tparams = _team_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game_key,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
        require_attribution=False,
    )
    sfw, sparams = _solo_score_where(
        lo=lo if not vacuous else "9999-99-99",
        hi=hi,
        game=game_key,
        play_mode=play_mode,
        include_archived=include_archived,
        min_size=min_size,
        max_size=max_size,
    )
    volume = {
        "team_plays": 0,
        "matches": 0,
        "shares": 0,
        "unique_players": 0,
        "unique_groups": 0,
        "avg_time_used": 0.0,
        "avg_roster_size": 0.0,
        "per_day": [],
    }
    if not vacuous:
        t_cnt = db._execute(f"SELECT COUNT(*) AS c {tfw}", tuple(tparams), fetch="one")
        m_cnt = db._execute(
            f"SELECT COUNT(DISTINCT cts.match_key) AS c {tfw} AND cts.match_key IS NOT NULL",
            tuple(tparams),
            fetch="one",
        )
        s_cnt = db._execute(f"SELECT COUNT(*) AS c, COUNT(DISTINCT cs.player_id) AS u {sfw}", tuple(sparams), fetch="one")
        g_cnt = db._execute(
            f"SELECT COUNT(DISTINCT cts.group_id) AS c {tfw} AND cts.group_id IS NOT NULL",
            tuple(tparams),
            fetch="one",
        )
        avg_row = db._execute(
            f"SELECT AVG(cts.time_used) AS tu, AVG({_roster_n_team()}) AS rs {tfw}",
            tuple(tparams),
            fetch="one",
        )
        per_day = db._execute(
            f"SELECT substr(cts.played_at, 1, 10) AS date, COUNT(*) AS plays {tfw} "
            "GROUP BY date ORDER BY date DESC LIMIT ?",
            tuple(tparams) + (_PER_DAY_LIMIT,),
            fetch="all",
        )
        volume = {
            "team_plays": int(t_cnt["c"] or 0) if t_cnt else 0,
            "matches": int(m_cnt["c"] or 0) if m_cnt else 0,
            "shares": int(s_cnt["c"] or 0) if s_cnt else 0,
            "unique_players": int(s_cnt["u"] or 0) if s_cnt else 0,
            "unique_groups": int(g_cnt["c"] or 0) if g_cnt else 0,
            "avg_time_used": round(float(avg_row["tu"] or 0), 2) if avg_row else 0.0,
            "avg_roster_size": round(float(avg_row["rs"] or 0), 2) if avg_row else 0.0,
            "per_day": [{"date": r["date"], "plays": int(r["plays"])} for r in (per_day or [])],
        }

    by_mode = []
    by_difficulty = []
    results = []
    if not vacuous:
        by_mode = [
            {"play_mode": r["play_mode"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT cts.play_mode AS play_mode, COUNT(*) AS plays {tfw} GROUP BY cts.play_mode",
                tuple(tparams),
                fetch="all",
            ) or []
        ]
        by_difficulty = [
            {"difficulty": r["difficulty"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT COALESCE(cts.difficulty, '') AS difficulty, COUNT(*) AS plays {tfw} "
                "GROUP BY difficulty",
                tuple(tparams),
                fetch="all",
            ) or []
        ]
        results = [
            {"result": r["result"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT cts.result AS result, COUNT(*) AS plays {tfw} GROUP BY cts.result",
                tuple(tparams),
                fetch="all",
            ) or []
        ]

    top_players = tournament_leaderboard(
        db,
        board="individual",
        use_active=False,
        game=game_key,
        period=period,
        limit=_TOP_LIST_LIMIT,
        play_mode=play_mode,
        min_size=min_size,
        max_size=max_size,
        include_archived=include_archived,
        today=today,
    )
    top_teams_raw = tournament_leaderboard(
        db,
        board="team",
        use_active=False,
        game=game_key,
        period=period,
        limit=_TOP_LIST_LIMIT,
        play_mode=play_mode,
        min_size=min_size,
        max_size=max_size,
        include_archived=include_archived,
        today=today,
    )
    top_teams = [
        {
            "group_id": r.get("group_id"),
            "group_name": r.get("group_name"),
            "score": r.get("score"),
            "played_at": r.get("played_at"),
            "id": r.get("id"),
        }
        for r in top_teams_raw
    ]

    return {
        "game": game_key,
        "health": health,
        "volume": volume,
        "by_mode": by_mode,
        "by_difficulty": by_difficulty,
        "results": results,
        "top_players": top_players,
        "top_teams": top_teams,
        "window": {"from": lo, "to_exclusive": hi},
    }


def get_tournament_stats(
    db: Database,
    tournament_id: int,
    *,
    period: str = "alltime",
    game: str = "all",
    today: Optional[date] = None,
):
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    if not row:
        raise HTTPException(404, "Tournament not found")
    trow = dict(row)
    board = _TYPE_TO_BOARD[trow["type"]]

    window = effective_window(
        db,
        board=board,
        tournament_id=tournament_id,
        use_active=False,
        period=period,
        today=today,
    )
    lo, hi = window.get("from"), window.get("to_exclusive")
    vacuous = lo is not None and hi is not None and lo >= hi

    total_plays = tournament_leaderboard_count(
        db,
        board=board,
        tournament_id=tournament_id,
        use_active=False,
        period=period,
        game=game,
        today=today,
    )
    entrants = tournament_entrant_count(db, tournament_id) if not vacuous else 0

    totals = {
        "plays": total_plays,
        "entrants": entrants,
        "unique_groups": None,
        "unique_players": None,
        "best_score": 0.0,
        "avg_score": 0.0,
    }
    if board == "team":
        totals["unique_groups"] = entrants
    else:
        totals["unique_players"] = entrants

    if not vacuous and total_plays > 0:
        from_where, params = _build(
            board,
            game=game,
            lo=lo,
            hi=hi,
            tournament=trow,
            company_id=None,
            group_id=None,
            play_mode=None,
            min_size=None,
            max_size=None,
            two_card=None,
            include_archived=False,
            difficulty=None,
        )
        if board == "team":
            agg = db._execute(
                f"SELECT MAX(cts.score) AS best, AVG(cts.score) AS avg {from_where}",
                tuple(params),
                fetch="one",
            )
        else:
            agg = db._execute(
                f"SELECT MAX(cs.score) AS best, AVG(cs.score) AS avg {from_where}",
                tuple(params),
                fetch="one",
            )
        if agg:
            totals["best_score"] = float(agg["best"] or 0)
            totals["avg_score"] = round(float(agg["avg"] or 0), 2)

    by_game = []
    by_mode = []
    by_day = []
    if not vacuous:
        from_where, params = _build(
            board,
            game="all",
            lo=lo,
            hi=hi,
            tournament=trow,
            company_id=None,
            group_id=None,
            play_mode=None,
            min_size=None,
            max_size=None,
            two_card=None,
            include_archived=False,
            difficulty=None,
        )
        played_col = "cts.played_at" if board == "team" else "cs.played_at"
        game_col = "cts.game" if board == "team" else "cs.game"
        score_col = "cts.score" if board == "team" else "cs.score"
        mode_col = "cts.play_mode" if board == "team" else "cs.play_mode"
        if game != "all":
            from_where += f" AND {game_col} = ?"
            params = list(params) + [game]
            total_plays = tournament_leaderboard_count(
                db,
                board=board,
                tournament_id=tournament_id,
                use_active=False,
                period=period,
                game=game,
                today=today,
            )
            totals["plays"] = total_plays

        by_game = [
            {
                "game": r["game"],
                "plays": int(r["plays"]),
                "best": float(r["best"] or 0),
            }
            for r in db._execute(
                f"SELECT {game_col} AS game, COUNT(*) AS plays, MAX({score_col}) AS best "
                f"{from_where} GROUP BY {game_col} ORDER BY plays DESC",
                tuple(params),
                fetch="all",
            ) or []
        ]
        by_mode = [
            {"play_mode": r["play_mode"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT {mode_col} AS play_mode, COUNT(*) AS plays {from_where} "
                f"GROUP BY {mode_col}",
                tuple(params),
                fetch="all",
            ) or []
        ]
        by_day = [
            {"date": r["date"], "plays": int(r["plays"])}
            for r in db._execute(
                f"SELECT substr({played_col}, 1, 10) AS date, COUNT(*) AS plays {from_where} "
                "GROUP BY date ORDER BY date",
                tuple(params),
                fetch="all",
            ) or []
        ]

    top = tournament_leaderboard(
        db,
        board=board,
        tournament_id=tournament_id,
        use_active=False,
        period=period,
        game=game,
        limit=_TOP_LIST_LIMIT,
        today=today,
        add_rank=True,
    )
    if board == "team":
        top = dashboard.enrich_team_rows(top)

    return {
        "tournament": {
            "id": trow["id"],
            "name": trow["name"],
            "type": trow["type"],
            "scope": trow["scope"],
            "starts_at": trow["starts_at"],
            "ends_at": trow["ends_at"],
            "status": trow["status"],
        },
        "window": window,
        "totals": totals,
        "by_game": by_game,
        "by_mode": by_mode,
        "by_day": by_day,
        "top": top,
    }
