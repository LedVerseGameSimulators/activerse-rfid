"""Dashboard queries — leaderboard, stats, health, player history."""
import json

from .database import Database


def get_health(db: Database):
    return db.get_game_health_all()


def get_leaderboard(db: Database, game: str = "all", period: str = "alltime",
                    limit: int = 20, board: str = "individual"):
    if board == "team":
        rows = db.get_team_leaderboard(game, period, limit)
        for r in rows:
            try:
                members = json.loads(r.get("members_json") or "[]")
            except json.JSONDecodeError:
                members = []
            r["members"] = members
            r["player_name"] = ", ".join(
                m.get("name") or f"#{m.get('player_id')}" for m in members
            ) or f"Team ({r.get('member_count', '?')})"
            r["score"] = r.get("final_score") if r.get("final_score") is not None else r.get("score")
        return rows
    return db.get_leaderboard(game, period, limit)


def get_stats(db: Database):
    return db.get_stats()


def get_player_dashboard(db: Database, player_id: int):
    return db.get_player_history(player_id)
