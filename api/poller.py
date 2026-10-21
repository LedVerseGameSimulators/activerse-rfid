"""
Background poller — polls game APIs every POLL_INTERVAL_SECONDS.
Pulls /health and /scores?since= from each game machine.
Team roster: explode each card score into a team row + N equal shares.
"""
import asyncio
import hashlib
import json
from datetime import datetime

import httpx
from loguru import logger

from .config import GAME_REGISTRY, POLL_INTERVAL_SECONDS
from .database import Database

_last_polled: dict[str, str] = {}
_running = False


def _effective_scores(raw, final):
    """If final is missing/0 but raw present, use raw for both (hex gap)."""
    try:
        raw_f = float(raw or 0)
    except (TypeError, ValueError):
        raw_f = 0.0
    try:
        final_f = float(final or 0)
    except (TypeError, ValueError):
        final_f = 0.0
    if final_f == 0 and raw_f != 0:
        final_f = raw_f
    return raw_f, final_f


def _parse_roster_player_ids(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [int(x) for x in value]
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning(f"Invalid roster_player_ids JSON: {e!r}")
            return None
        if isinstance(parsed, list):
            return [int(x) for x in parsed]
    return None


def _match_key(game: str, played_at: str, card_id: str, card_id2: str) -> str:
    payload = f"{game}|{played_at or ''}|{card_id}|{card_id2}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _resolve_card_context(
    db: Database,
    card_id: str,
    played_at: str,
    stamped_session_id,
    stamped_group_id,
    roster_size_at_play,
    roster_player_ids_raw,
):
    """Resolve session, group, roster snapshot, and N for one card slot."""
    cid = card_id or ""
    roster_ids = _parse_roster_player_ids(roster_player_ids_raw)

    session = None
    if stamped_session_id is not None:
        session = db.get_session(stamped_session_id)
    if session is None and cid:
        session = db.get_session_for_card_at(cid, played_at)

    if session:
        sid = session["id"]
        group_id = stamped_group_id
        if group_id is None:
            group_id = session.get("group_id")
        if group_id is None:
            group_id = db.get_group_id_for_player(session["player_id"])
        company_id = session.get("company_id")

        roster = []
        if roster_ids:
            for pid in roster_ids:
                rows = db.search_custom_tb_by_id(pid)
                name = rows[0]["name"] if rows else ""
                roster.append({
                    "player_id": pid,
                    "name": name,
                    "is_payer": 1 if session.get("player_id") == pid else 0,
                })
        else:
            roster = db.get_session_roster(sid)
            if not roster:
                roster = [{
                    "player_id": session["player_id"],
                    "name": session.get("player_name") or "",
                    "is_payer": 1,
                }]
    else:
        sid = None
        group_id = None
        company_id = None
        roster = []

    if roster_size_at_play is not None:
        try:
            n = max(int(roster_size_at_play), 1)
        except (TypeError, ValueError):
            n = max(len(roster), 1)
    elif roster_ids:
        n = max(len(roster_ids), 1)
    else:
        n = max(len(roster), 1)

    members_snap = [
        {"player_id": m["player_id"], "name": m.get("name") or ""}
        for m in roster
    ] if roster else []

    return {
        "session_id": sid,
        "group_id": group_id,
        "company_id": company_id,
        "roster": roster,
        "members_snap": members_snap,
        "n": n,
        "roster_size_at_play": roster_size_at_play if roster_size_at_play is not None else n,
    }


def _ingest_card_score(
    db: Database,
    ctx: dict,
    card_id: str,
    player_slot: int,
    raw_score,
    final_score,
    slot_ctx: dict,
    *,
    play_mode=None,
    two_card_play: bool = False,
    match_key=None,
    opponent_group_id=None,
    opponent_card_id=None,
):
    raw_f, final_f = _effective_scores(raw_score, final_score)
    cid = card_id or ""

    sid = slot_ctx["session_id"]
    n = slot_ctx["n"]
    members_snap = slot_ctx["members_snap"]
    roster = slot_ctx["roster"]
    company_id = slot_ctx["company_id"]
    group_id = slot_ctx["group_id"]
    roster_size_at_play = slot_ctx["roster_size_at_play"]

    ingest_ctx = {
        **ctx,
        "play_mode": play_mode,
        "roster_size_at_play": roster_size_at_play,
        "two_card_play": two_card_play,
        "match_key": match_key,
        "opponent_group_id": opponent_group_id,
        "opponent_card_id": opponent_card_id,
    }

    team_score_id = db.upsert_central_team_score({
        **ingest_ctx,
        "session_id": sid,
        "card_id": cid or None,
        "player_slot": player_slot,
        "score": raw_f,
        "final_score": final_f,
        "member_count": n,
        "members_json": json.dumps(members_snap),
        "company_id": company_id,
        "group_id": group_id,
    })

    share_raw = round(raw_f / n, 4)
    share_final = round(final_f / n, 4)

    if roster:
        for m in roster:
            db.upsert_central_score({
                **ingest_ctx,
                "player_id": m["player_id"],
                "card_id": cid or None,
                "player_slot": player_slot,
                "session_id": sid,
                "team_score_id": team_score_id,
                "score": share_raw,
                "final_score": share_final,
                "company_id": company_id,
                "group_id": group_id,
            })
    else:
        db.upsert_central_score({
            **ingest_ctx,
            "player_id": None,
            "card_id": cid or None,
            "player_slot": player_slot,
            "session_id": sid,
            "team_score_id": team_score_id,
            "score": share_raw,
            "final_score": share_final,
            "company_id": company_id,
            "group_id": group_id,
        })


def _ingest_game_row(db: Database, game: str, row: dict):
    played_at = row.get("ts") or row.get("played_at")
    ctx = {
        "game": game,
        "level": row.get("level", ""),
        "end_level": row.get("end_level", ""),
        "level_file": row.get("level_file", ""),
        "end_level_file": row.get("end_level_file", ""),
        "life": row.get("life"),
        "lives_start": row.get("lives_start"),
        "result": row.get("result"),
        "time_used": row.get("time_used", 0),
        "levels_cleared": row.get("levels_cleared", 0),
        "difficulty": row.get("difficulty", ""),
        "started_at": row.get("started_at", ""),
        "played_at": played_at,
    }

    card_id = row.get("card_id") or ""
    card_id2 = row.get("card_id2") or ""
    play_mode = row.get("play_mode")
    two_card = bool(card_id2 and card_id2 != card_id)
    if two_card and play_mode and play_mode != "team_battle":
        logger.warning(
            f"Two-card play for {game} with play_mode={play_mode!r} (expected team_battle)"
        )
    match_key = _match_key(game, played_at or "", card_id, card_id2) if two_card else None

    ctx1 = _resolve_card_context(
        db, card_id, played_at,
        row.get("session_id"), row.get("group_id"),
        row.get("roster_size_at_play"), row.get("roster_player_ids"),
    )
    ctx2 = None
    if two_card:
        ctx2 = _resolve_card_context(
            db, card_id2, played_at,
            row.get("session_id2"), row.get("group_id2"),
            row.get("roster_size_at_play2"), row.get("roster_player_ids2"),
        )

    ingest_second = two_card
    if two_card and ctx1.get("session_id") and ctx1["session_id"] == ctx2.get("session_id"):
        logger.warning(
            f"Two-card play with same session #{ctx1['session_id']} — ingesting slot 1 only"
        )
        ingest_second = False
        match_key = None

    two_card_play = ingest_second

    _ingest_card_score(
        db, ctx, card_id, 1,
        row.get("score", 0), row.get("final_score", 0),
        ctx1,
        play_mode=play_mode,
        two_card_play=two_card_play,
        match_key=match_key if two_card_play else None,
        opponent_group_id=ctx2.get("group_id") if ctx2 else None,
        opponent_card_id=card_id2 if ingest_second else None,
    )

    if ingest_second and ctx2:
        _ingest_card_score(
            db, ctx, card_id2, 2,
            row.get("score2", 0), row.get("final_score2", 0),
            ctx2,
            play_mode=play_mode,
            two_card_play=True,
            match_key=match_key,
            opponent_group_id=ctx1.get("group_id"),
            opponent_card_id=card_id,
        )


async def _poll_game(db: Database, game: str, base_url: str):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{base_url}/health")
            data = resp.json()
            status = "running" if data.get("status") == "ok" else "idle"
            active_id = ""
            stats = data.get("stats") or {}
            if stats.get("active_games", 0) > 0:
                status = "running"
            db.update_game_health(game, status, active_id)
        except Exception as e:
            logger.warning(f"Health check failed for {game}: {e}")
            db.update_game_health(game, "down")

        since = _last_polled.get(game) or db.get_poll_cursor(game) or "2000-01-01T00:00:00"
        try:
            resp = await client.get(f"{base_url}/scores", params={"since": since})
            payload = resp.json()
            if payload.get("success"):
                max_ts = since
                for row in payload.get("scores") or []:
                    _ingest_game_row(db, game, row)
                    played_at = row.get("ts") or row.get("played_at")
                    if played_at and played_at > max_ts:
                        max_ts = played_at
                if payload.get("scores"):
                    logger.info(f"Polled {len(payload['scores'])} scores from {game}")
                _last_polled[game] = max_ts
                db.set_poll_cursor(game, max_ts)
        except Exception as e:
            logger.warning(f"Score poll failed for {game}: {e}")


async def poll_all(db: Database):
    tasks = []
    for game, info in GAME_REGISTRY.items():
        tasks.append(_poll_game(db, game, info["api"]))
    await asyncio.gather(*tasks)


async def poller_loop(db: Database):
    global _running
    _running = True
    logger.info(f"Poller started (interval={POLL_INTERVAL_SECONDS}s)")
    while _running:
        try:
            await poll_all(db)
        except Exception as e:
            logger.error(f"Poller cycle error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def stop_poller():
    global _running
    _running = False
