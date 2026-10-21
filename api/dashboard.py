"""Dashboard queries — leaderboard, stats, health, player history."""
import json
from typing import Optional

from .database import Database


def get_health(db: Database):
    return db.get_game_health_all()


def get_leaderboard(db: Database, game: str = "all", period: str = "alltime",
                    limit: int = 20, board: str = "individual",
                    company_id: Optional[int] = None, group_id: Optional[int] = None,
                    play_mode: Optional[str] = None, min_size: Optional[int] = None,
                    max_size: Optional[int] = None, two_card: Optional[bool] = None):
    lb_kwargs = dict(
        company_id=company_id, group_id=group_id, play_mode=play_mode,
        min_size=min_size, max_size=max_size, two_card=two_card,
    )
    if board == "team":
        rows = db.get_team_leaderboard(game, period, limit, **lb_kwargs)
        for r in rows:
            try:
                members = json.loads(r.get("members_json") or "[]")
            except json.JSONDecodeError:
                members = []
            r["members"] = members
            r["player_name"] = ", ".join(
                m.get("name") or f"#{m.get('player_id')}" for m in members
            ) or f"Team ({r.get('member_count', '?')})"
        return rows
    return db.get_leaderboard(game, period, limit, **lb_kwargs)


def get_stats(db: Database):
    return db.get_stats()


def get_player_dashboard(db: Database, player_id: int):
    return db.get_player_history(player_id)
