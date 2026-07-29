"""
Background poller — polls game APIs every POLL_INTERVAL_SECONDS.
Pulls /health and /scores?since= from each game machine.
Team roster: explode each card score into a team row + N equal shares.
"""
import asyncio
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


def _ingest_card_score(db: Database, ctx: dict, card_id: str, player_slot: int,
                       raw_score, final_score):
    raw_f, final_f = _effective_scores(raw_score, final_score)
    cid = card_id or ""

    session = db.get_session_for_card_at(cid, ctx.get("played_at")) if cid else None
    sid = session["id"] if session else None

    roster = db.get_session_roster(sid) if sid else []
    if not roster and session:
        roster = [{
            "player_id": session["player_id"],
            "name": session.get("player_name") or "",
            "is_payer": 1,
        }]
    if not roster and cid:
        players = db.search_custom_by_field("card_id", cid)
        if players:
            roster = [{
                "player_id": players[0]["custom_id"],
                "name": players[0].get("name") or "",
                "is_payer": 1,
            }]

    n = max(len(roster), 1)
    members_snap = [
        {"player_id": m["player_id"], "name": m.get("name") or ""}
        for m in roster
    ] if roster else []

    team_score_id = db.upsert_central_team_score({
        **ctx,
        "session_id": sid,
        "card_id": cid or None,
        "player_slot": player_slot,
        "score": raw_f,
        "final_score": final_f,
        "member_count": n,
        "members_json": json.dumps(members_snap),
        "company_id": (session or {}).get("company_id"),
    })

    share_raw = round(raw_f / n, 4)
    share_final = round(final_f / n, 4)
    company_id = (session or {}).get("company_id")

    if roster:
        for m in roster:
            db.upsert_central_score({
                **ctx,
                "player_id": m["player_id"],
                "card_id": cid or None,
                "player_slot": player_slot,
                "session_id": sid,
                "team_score_id": team_score_id,
                "score": share_raw,
                "final_score": share_final,
                "company_id": company_id,
            })
    else:
        # Guest / unknown card — single anonymous row
        db.upsert_central_score({
            **ctx,
            "player_id": None,
            "card_id": cid or None,
            "player_slot": player_slot,
            "session_id": sid,
            "team_score_id": team_score_id,
            "score": share_raw,
            "final_score": share_final,
            "company_id": company_id,
        })


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
                    played_at = row.get("ts") or row.get("played_at")
                    ctx = {
                        "game": game,
                        "level": row.get("level", ""),
                        "end_level": row.get("end_level", ""),
                        "life": row.get("life"),
                        "lives_start": row.get("lives_start"),
                        "result": row.get("result"),
                        "time_used": row.get("time_used", 0),
                        "levels_cleared": row.get("levels_cleared", 0),
                        "difficulty": row.get("difficulty", ""),
                        "started_at": row.get("started_at", ""),
                        "played_at": played_at,
                    }

                    _ingest_card_score(
                        db, ctx,
                        row.get("card_id") or "",
                        1,
                        row.get("score", 0),
                        row.get("final_score", 0),
                    )

                    if row.get("multiplayer") and (row.get("card_id2") or ""):
                        _ingest_card_score(
                            db, ctx,
                            row.get("card_id2") or "",
                            2,
                            row.get("score2", 0),
                            row.get("final_score2", 0),
                        )

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
