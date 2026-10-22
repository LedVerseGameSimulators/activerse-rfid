"""Dashboard queries — leaderboard, stats, health, player history."""
import json
from typing import Optional

from .database import Database
from .leaderboard import tournament_leaderboard


def get_health(db: Database):
    return db.get_game_health_all()


def enrich_team_rows(rows: list) -> list:
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


def get_leaderboard(db: Database, game: str = "all", period: str = "alltime",
                    limit: int = 20, board: str = "individual",
                    company_id: Optional[int] = None, group_id: Optional[int] = None,
                    play_mode: Optional[str] = None, min_size: Optional[int] = None,
                    max_size: Optional[int] = None, two_card: Optional[bool] = None,
                    include_archived: bool = False,
                    tournament_id: Optional[int] = None,
                    offset: int = 0,
                    difficulty: Optional[str] = None):
    if board not in ("individual", "team"):
        from fastapi import HTTPException
        raise HTTPException(422, "board must be individual or team")
    if limit <= 0:
        limit = 20
    if min_size is not None and min_size < 0:
        min_size = None
    if max_size is not None and max_size < 0:
        max_size = None
    lb_kwargs = dict(
        game=game,
        period=period,
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
        tournament_id=tournament_id,
        use_active=True,
        add_rank=True,
    )
    try:
        if board == "team":
            rows = tournament_leaderboard(db, board="team", **lb_kwargs)
            return enrich_team_rows(rows)
        return tournament_leaderboard(db, board="individual", **lb_kwargs)
    except LookupError:
        from fastapi import HTTPException
        raise HTTPException(404, "Tournament not found")
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(400, str(e))


def get_stats(db: Database):
    return db.get_stats()


def get_player_dashboard(db: Database, player_id: int):
    return db.get_player_history(player_id)
