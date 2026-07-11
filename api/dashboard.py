"""Dashboard queries — leaderboard, stats, health, player history."""
from .database import Database


def get_health(db: Database):
    return db.get_game_health_all()


def get_leaderboard(db: Database, game: str = "all", period: str = "alltime", limit: int = 20):
    return db.get_leaderboard(game, period, limit)


def get_stats(db: Database):
    return db.get_stats()


def get_player_dashboard(db: Database, player_id: int):
    return db.get_player_history(player_id)
