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
        since = _last_polled.get(game, "2000-01-01T00:00:00")
        try:
            resp = await client.get(f"{base_url}/scores", params={"since": since})
            payload = resp.json()
            if payload.get("success"):
                for row in payload.get("scores") or []:
                    card_id = row.get("card_id") or ""
                    player_id = None
                    session_id = None
                    if card_id:
                        players = db.search_custom_by_field("card_id", card_id)
                        if players:
                            player_id = players[0]["custom_id"]
                            sess = db.get_active_session_by_card(card_id)
                            if sess:
                                session_id = sess["id"]
                    db.upsert_central_score({
                        "player_id": player_id,
                        "card_id": card_id or None,
                        "session_id": session_id,
                        "game": game,
                        "level": row.get("level", ""),
                        "score": row.get("score", 0),
                        "score2": row.get("score2", 0),
                        "life": row.get("life"),
                        "result": row.get("result"),
                        "time_used": row.get("time_used", 0),
                        "played_at": row.get("ts") or row.get("played_at"),
                    })
                if payload.get("scores"):
                    logger.info(f"Polled {len(payload['scores'])} scores from {game}")
                _last_polled[game] = datetime.now().isoformat(timespec="seconds")
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
