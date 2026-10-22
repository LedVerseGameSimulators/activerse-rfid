"""Shared tournament-aware leaderboard queries (P4a)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .database import Database

_BOARD_TO_TYPE = {"individual": "solo", "team": "team"}
_TYPE_TO_BOARD = {"solo": "individual", "team": "team"}
_LEGACY_SYSTEM_KEY = {"individual": "legacy_solo", "team": "legacy_team"}
_ACTIVE_SETTING = {
    "individual": "active_global_solo_tournament_id",
    "team": "active_global_team_tournament_id",
}


def period_bounds(period: str, today: date) -> tuple[Optional[str], Optional[str]]:
    """Return (lo_inclusive_date, hi_exclusive_date) as YYYY-MM-DD or None."""
    if period == "today":
        return today.isoformat(), (today + timedelta(days=1)).isoformat()
    if period == "week":
        return (today - timedelta(days=7)).isoformat(), None
    if period == "month":
        return today.replace(day=1).isoformat(), None
    return None, None


def _tournament_window_bounds(tournament: Optional[dict]) -> tuple[Optional[str], Optional[str]]:
    if not tournament:
        return None, None
    lo = tournament.get("starts_at")
    hi = None
    if tournament.get("ends_at"):
        end = date.fromisoformat(tournament["ends_at"])
        hi = (end + timedelta(days=1)).isoformat()
    return lo, hi


def _merge_bounds(
    period_lo: Optional[str],
    period_hi: Optional[str],
    tour_lo: Optional[str],
    tour_hi: Optional[str],
) -> tuple[Optional[str], Optional[str], bool]:
    """Merge period and tournament windows. Returns (lo, hi, vacuous)."""
    los = [x for x in (period_lo, tour_lo) if x]
    his = [x for x in (period_hi, tour_hi) if x]
    lo = max(los) if los else None
    hi = min(his) if his else None
    if lo is not None and hi is not None and lo >= hi:
        return lo, hi, True
    return lo, hi, False


def _load_tournament(db: Database, tournament_id: int) -> Optional[dict]:
    row = db._execute(
        "SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetch="one"
    )
    return dict(row) if row else None


def resolve_tournament(
    db: Database,
    tournament_id: Optional[int],
    board: str,
    use_active: bool,
) -> Optional[dict]:
    """Resolve tournament row for leaderboard window / company scope."""
    ttype = _BOARD_TO_TYPE.get(board, "solo")

    if tournament_id is not None:
        row = _load_tournament(db, tournament_id)
        if not row:
            raise LookupError("Tournament not found")
        if row["type"] != ttype:
            raise ValueError(
                f"tournament is {row['type']}; use board={_TYPE_TO_BOARD[row['type']]}"
            )
        return row

    if not use_active:
        return None

    settings = db.get_all_settings()
    key = _ACTIVE_SETTING[board]
    raw = settings.get(key)
    row = None
    if raw:
        try:
            tid = int(raw)
            row = _load_tournament(db, tid)
        except (TypeError, ValueError):
            row = None
    if row and row.get("scope") == "global" and row.get("status") != "archived":
        return row

    legacy_key = _LEGACY_SYSTEM_KEY[board]
    fallback = db._execute(
        "SELECT * FROM tournaments WHERE system_key = ?", (legacy_key,), fetch="one"
    )
    if fallback:
        logger.warning(
            "Active global {} tournament invalid or missing; using legacy {}",
            board,
            legacy_key,
        )
        return dict(fallback)
    return None


def _roster_n_solo() -> str:
    return "MAX(COALESCE(cs.roster_size_at_play, t.member_count, 1), 1)"


def _roster_n_team() -> str:
    return "MAX(COALESCE(cts.roster_size_at_play, cts.member_count, 1), 1)"


def _build(
    board: str,
    *,
    game: str,
    lo: Optional[str],
    hi: Optional[str],
    tournament: Optional[dict],
    company_id: Optional[int],
    group_id: Optional[int],
    play_mode: Optional[str],
    min_size: Optional[int],
    max_size: Optional[int],
    two_card: Optional[bool],
    include_archived: bool,
    difficulty: Optional[str],
) -> tuple[str, list]:
    """Build FROM/JOIN/WHERE SQL and params (no SELECT/ORDER/LIMIT)."""
    params: list[Any] = []
    if board == "team":
        clauses = ["cts.session_id IS NOT NULL", "cts.group_id IS NOT NULL"]
        from_sql = (
            "FROM central_team_scores cts "
            "LEFT JOIN groups g ON g.id = cts.group_id "
        )
        played_col = "cts.played_at"
        roster_n = _roster_n_team()
        if not include_archived:
            clauses.append("(g.id IS NULL OR g.archived_at IS NULL)")
        if game != "all":
            clauses.append("cts.game = ?")
            params.append(game)
        if lo is not None:
            clauses.append(f"{played_col} >= ?")
            params.append(lo)
        if hi is not None:
            clauses.append(f"{played_col} < ?")
            params.append(hi)
        if tournament and tournament.get("scope") == "company":
            clauses.append("cts.company_id = ?")
            params.append(tournament["company_id"])
        if company_id is not None:
            clauses.append("cts.company_id = ?")
            params.append(company_id)
        if group_id is not None:
            clauses.append("cts.group_id = ?")
            params.append(group_id)
        if play_mode is not None:
            clauses.append("cts.play_mode = ?")
            params.append(play_mode)
        if min_size is not None:
            clauses.append(f"{roster_n} >= ?")
            params.append(max(int(min_size), 0))
        if max_size is not None:
            clauses.append(f"{roster_n} <= ?")
            params.append(max(int(max_size), 0))
        if two_card is True:
            clauses.append("cts.two_card_play = 1")
        elif two_card is False:
            clauses.append("COALESCE(cts.two_card_play, 0) = 0")
        if difficulty is not None:
            clauses.append("LOWER(COALESCE(cts.difficulty,'')) = LOWER(?)")
            params.append(difficulty)
    else:
        clauses = ["cs.player_id IS NOT NULL"]
        from_sql = (
            "FROM central_scores cs "
            "LEFT JOIN groups g ON g.id = cs.group_id "
            "LEFT JOIN central_team_scores t ON t.id = cs.team_score_id "
        )
        played_col = "cs.played_at"
        roster_n = _roster_n_solo()
        if not include_archived:
            clauses.append("(cs.group_id IS NULL OR g.archived_at IS NULL)")
        if game != "all":
            clauses.append("cs.game = ?")
            params.append(game)
        if lo is not None:
            clauses.append(f"{played_col} >= ?")
            params.append(lo)
        if hi is not None:
            clauses.append(f"{played_col} < ?")
            params.append(hi)
        if tournament and tournament.get("scope") == "company":
            clauses.append("cs.company_id = ?")
            params.append(tournament["company_id"])
        if company_id is not None:
            clauses.append("cs.company_id = ?")
            params.append(company_id)
        if group_id is not None:
            clauses.append("cs.group_id = ?")
            params.append(group_id)
        if play_mode is not None:
            clauses.append("cs.play_mode = ?")
            params.append(play_mode)
        if min_size is not None:
            clauses.append(f"{roster_n} >= ?")
            params.append(max(int(min_size), 0))
        if max_size is not None:
            clauses.append(f"{roster_n} <= ?")
            params.append(max(int(max_size), 0))
        if two_card is True:
            clauses.append("cs.two_card_play = 1")
        elif two_card is False:
            clauses.append("COALESCE(cs.two_card_play, 0) = 0")
        if difficulty is not None:
            clauses.append("LOWER(COALESCE(cs.difficulty,'')) = LOWER(?)")
            params.append(difficulty)

    where = " AND ".join(clauses)
    return f"{from_sql} WHERE {where}", params


def tournament_leaderboard(
    db: Database,
    *,
    board: str = "individual",
    tournament_id: Optional[int] = None,
    use_active: bool = False,
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
    today: Optional[date] = None,
    add_rank: bool = False,
) -> list[dict]:
    if min_size is not None and max_size is not None and min_size > max_size:
        return []

    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    today = today or date.today()

    tournament = resolve_tournament(db, tournament_id, board, use_active)
    p_lo, p_hi = period_bounds(period, today)
    t_lo, t_hi = _tournament_window_bounds(tournament)
    lo, hi, vacuous = _merge_bounds(p_lo, p_hi, t_lo, t_hi)
    if vacuous:
        return []

    from_where, params = _build(
        board,
        game=game,
        lo=lo,
        hi=hi,
        tournament=tournament,
        company_id=company_id,
        group_id=group_id,
        play_mode=play_mode,
        min_size=min_size,
        max_size=max_size,
        two_card=two_card,
        include_archived=include_archived,
        difficulty=difficulty,
    )

    if board == "team":
        select = (
            "SELECT cts.*, g.name AS group_name, g.kind AS group_kind "
        )
        order = " ORDER BY cts.score DESC, cts.id ASC"
    else:
        select = (
            "SELECT cs.*, ci.name AS player_name, g.name AS group_name, g.kind AS group_kind "
        )
        from_where = from_where.replace(
            "FROM central_scores cs",
            "FROM central_scores cs "
            "LEFT JOIN custom_info ci ON ci.custom_id = cs.player_id",
            1,
        )
        order = " ORDER BY cs.score DESC, cs.id ASC"

    qparams = list(params) + [limit, offset]
    rows = db._execute(
        f"{select}{from_where}{order} LIMIT ? OFFSET ?",
        tuple(qparams),
        fetch="all",
    )
    out = [dict(r) for r in rows] if rows else []
    if add_rank:
        for i, row in enumerate(out):
            row["rank"] = offset + i + 1
    return out


def tournament_leaderboard_count(
    db: Database,
    *,
    board: str = "individual",
    tournament_id: Optional[int] = None,
    use_active: bool = False,
    period: str = "alltime",
    game: str = "all",
    company_id: Optional[int] = None,
    group_id: Optional[int] = None,
    play_mode: Optional[str] = None,
    min_size: Optional[int] = None,
    max_size: Optional[int] = None,
    two_card: Optional[bool] = None,
    include_archived: bool = False,
    difficulty: Optional[str] = None,
    today: Optional[date] = None,
) -> int:
    """Same filters as tournament_leaderboard; returns total row count."""
    if min_size is not None and max_size is not None and min_size > max_size:
        return 0

    today = today or date.today()
    tournament = resolve_tournament(db, tournament_id, board, use_active)
    p_lo, p_hi = period_bounds(period, today)
    t_lo, t_hi = _tournament_window_bounds(tournament)
    lo, hi, vacuous = _merge_bounds(p_lo, p_hi, t_lo, t_hi)
    if vacuous:
        return 0

    from_where, params = _build(
        board,
        game=game,
        lo=lo,
        hi=hi,
        tournament=tournament,
        company_id=company_id,
        group_id=group_id,
        play_mode=play_mode,
        min_size=min_size,
        max_size=max_size,
        two_card=two_card,
        include_archived=include_archived,
        difficulty=difficulty,
    )
    row = db._execute(
        f"SELECT COUNT(*) AS c {from_where}",
        tuple(params),
        fetch="one",
    )
    return int(row["c"]) if row else 0


def effective_window(
    db: Database,
    *,
    board: str,
    tournament_id: Optional[int],
    use_active: bool,
    period: str,
    today: Optional[date] = None,
) -> dict:
    """Return {from, to_exclusive} for API envelope."""
    today = today or date.today()
    tournament = resolve_tournament(db, tournament_id, board, use_active)
    p_lo, p_hi = period_bounds(period, today)
    t_lo, t_hi = _tournament_window_bounds(tournament)
    lo, hi, _ = _merge_bounds(p_lo, p_hi, t_lo, t_hi)
    return {"from": lo, "to_exclusive": hi}
