"""
Background poller — polls game APIs every POLL_INTERVAL_SECONDS.
Pulls /health and /scores?since= from each game machine.
"""
import asyncio
from datetime import datetime

import httpx
from loguru import logger

from .config import GAME_REGISTRY, POLL_INTERVAL_SECONDS
from .database import Database

_last_polled: dict[str, str] = {}
_running = False


async def _poll_game(db: Database, game: str, base_url: str):
    async with httpx.AsyncClient(timeout=10) as client:
        # Health check
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

        # Scores pull
        since = _last_polled.get(game) or db.get_poll_cursor(game) or "2000-01-01T00:00:00"
        try:
            resp = await client.get(f"{base_url}/scores", params={"since": since})
            payload = resp.json()
            if payload.get("success"):
                max_ts = since
                for row in payload.get("scores") or []:
                    played_at = row.get("ts") or row.get("played_at")
                    # Shared per-session context (same for both players).
                    ctx = {
                        "session_id": None,
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

                    def _lookup(cid):
                        pid = sid = None
                        if cid:
                            players = db.search_custom_by_field("card_id", cid)
                            if players:
                                pid = players[0]["custom_id"]
                                sess = db.get_active_session_by_card(cid)
                                if sess:
                                    sid = sess["id"]
                        return pid, sid

                    # ── P1 row (always) ──
                    c1 = row.get("card_id") or ""
                    p1_id, s1 = _lookup(c1)
                    db.upsert_central_score({
                        **ctx,
                        "player_id": p1_id,
                        "card_id": c1 or None,
                        "player_slot": 1,
                        "session_id": s1,
                        "score": row.get("score", 0),
                        "final_score": row.get("final_score", 0),
                    })

                    # ── P2 row (only for a real 2P session) ──
                    if row.get("multiplayer") and (row.get("card_id2") or ""):
                        c2 = row.get("card_id2") or ""
                        p2_id, s2 = _lookup(c2)
                        db.upsert_central_score({
                            **ctx,
                            "player_id": p2_id,
                            "card_id": c2 or None,
                            "player_slot": 2,
                            "session_id": s2,
                            "score": row.get("score2", 0),
                            "final_score": row.get("final_score2", 0),
                        })

                    if played_at and played_at > max_ts:
                        max_ts = played_at
                if payload.get("scores"):
                    logger.info(f"Polled {len(payload['scores'])} scores from {game}")
                # Advance cursor to the newest row ACTUALLY seen (immune to
                # clock skew between this server and the game machine), and
                # persist it so a central restart resumes instead of re-pulling.
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
            logger.error(f"Poller error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


def stop_poller():
    global _running
    _running = False
