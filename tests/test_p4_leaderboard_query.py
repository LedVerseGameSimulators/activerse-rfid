"""P4a shared leaderboard query — windows, filters, wrappers."""
from datetime import date

import pytest

from api.leaderboard import (
    period_bounds,
    tournament_leaderboard,
    resolve_tournament,
)
from api import dashboard
from tests.test_step0_poller_and_leaderboard import _make_player


def _legacy_solo_id(db):
    row = db._execute(
        "SELECT id FROM tournaments WHERE system_key='legacy_solo'", fetch="one"
    )
    return int(row["id"])


def _legacy_team_id(db):
    row = db._execute(
        "SELECT id FROM tournaments WHERE system_key='legacy_team'", fetch="one"
    )
    return int(row["id"])


def test_migration_idempotent(db):
    c1 = db._execute("SELECT COUNT(*) AS c FROM tournaments", fetch="one")["c"]
    s1 = db._execute(
        "SELECT COUNT(*) AS c FROM settings WHERE key LIKE 'active_global_%_tournament_id'",
        fetch="one",
    )["c"]
    db._ensure_tables()
    c2 = db._execute("SELECT COUNT(*) AS c FROM tournaments", fetch="one")["c"]
    s2 = db._execute(
        "SELECT COUNT(*) AS c FROM settings WHERE key LIKE 'active_global_%_tournament_id'",
        fetch="one",
    )["c"]
    assert c1 == c2 == 2
    assert s1 == s2 == 2
    keys = {r["system_key"] for r in db._execute(
        "SELECT system_key FROM tournaments", fetch="all"
    )}
    assert keys == {"legacy_solo", "legacy_team"}


def test_migration_keeps_admin_active_choice(db):
    tid = db._executemany_return_id(
        "INSERT INTO tournaments (name, type, scope, status, created_at, updated_at) "
        "VALUES ('Oct', 'solo', 'global', 'active', 'x', 'x')",
        (),
    )
    db.set_setting("active_global_solo_tournament_id", str(tid))
    db._ensure_tables()
    val = db.get_all_settings()["active_global_solo_tournament_id"]
    assert val == str(tid)


def test_legacy_solo_covers_attributed_excludes_guests(db):
    p = _make_player(db, "555-p4a1", "Attrib")
    db.upsert_central_score({
        "player_id": p, "card_id": "P4A1", "game": "hoops",
        "played_at": "2026-10-20T12:00:00", "score": 10,
    })
    db.upsert_central_score({
        "player_id": p, "card_id": "P4A2", "game": "hoops",
        "played_at": "2026-06-01 12:00:00", "score": 11,
    })
    db.upsert_central_score({
        "player_id": p, "card_id": "P4A3", "game": "hoops",
        "played_at": None, "score": 12,
    })
    db.upsert_central_score({
        "player_id": None, "card_id": "P4GHOST", "game": "hoops",
        "played_at": "2026-10-20T12:00:00", "score": 999,
    })
    rows = tournament_leaderboard(
        db, board="individual", tournament_id=_legacy_solo_id(db), use_active=False, limit=50
    )
    cards = {r["card_id"] for r in rows}
    assert "P4A1" in cards and "P4A2" in cards and "P4A3" in cards
    assert "P4GHOST" not in cards


def test_legacy_team_requires_session_and_group(db):
    db.upsert_central_team_score({
        "session_id": 9, "card_id": "T1", "game": "hoops",
        "played_at": "2026-01-01", "score": 10, "member_count": 2,
        "members_json": "[]", "group_id": 5,
    })
    db.upsert_central_team_score({
        "session_id": None, "card_id": "T2", "game": "hoops",
        "played_at": "2026-01-01", "score": 20, "member_count": 2,
        "members_json": "[]", "group_id": 5,
    })
    rows = tournament_leaderboard(
        db, board="team", tournament_id=_legacy_team_id(db), use_active=False, limit=50
    )
    assert len(rows) == 1
    assert rows[0]["card_id"] == "T1"


def test_window_boundaries_t_vs_space(db):
    tid = db._executemany_return_id(
        "INSERT INTO tournaments (name, type, scope, status, starts_at, ends_at, created_at, updated_at) "
        "VALUES ('Oct', 'solo', 'global', 'active', '2026-10-01', '2026-10-31', 'x', 'x')",
        (),
    )
    p = _make_player(db, "555-p4w", "Win")
    fixtures = [
        ("2026-09-30T23:59:59", "OUT1"),
        ("2026-10-01 00:00:00", "IN1"),
        ("2026-10-31T23:59:59", "IN2"),
        ("2026-10-31 12:00:00", "IN3"),
        ("2026-11-01T00:00:00", "OUT2"),
    ]
    for played_at, card in fixtures:
        db.upsert_central_score({
            "player_id": p, "card_id": card, "game": "hoops",
            "played_at": played_at, "score": 1,
        })
    rows = tournament_leaderboard(
        db, board="individual", tournament_id=tid, use_active=False, limit=20
    )
    got = {r["card_id"] for r in rows}
    assert got == {"IN1", "IN2", "IN3"}


def test_vacuous_disjoint_window(db):
    p = _make_player(db, "555-p4v", "Vac")
    db.upsert_central_score({
        "player_id": p, "card_id": "VAC1", "game": "hoops",
        "played_at": "2026-01-01", "score": 5,
    })
    assert db.get_leaderboard(limit=5)
    tid = db._executemany_return_id(
        "INSERT INTO tournaments (name, type, scope, status, starts_at, ends_at, created_at, updated_at) "
        "VALUES ('Future', 'solo', 'global', 'active', '2099-01-01', '2099-12-31', 'x', 'x')",
        (),
    )
    assert tournament_leaderboard(
        db, board="individual", tournament_id=tid, use_active=False
    ) == []


def test_disjoint_period_and_tournament(db):
    p = _make_player(db, "555-p4d", "Dis")
    db.upsert_central_score({
        "player_id": p, "card_id": "DIS1", "game": "hoops",
        "played_at": "2026-12-01", "score": 1,
    })
    tid = db._executemany_return_id(
        "INSERT INTO tournaments (name, type, scope, status, starts_at, ends_at, created_at, updated_at) "
        "VALUES ('Oct', 'solo', 'global', 'active', '2026-10-01', '2026-10-31', 'x', 'x')",
        (),
    )
    rows = tournament_leaderboard(
        db, board="individual", tournament_id=tid, use_active=False,
        period="today", today=date(2026, 12, 1),
    )
    assert rows == []


def test_period_bounds_month_and_unknown(db):
    d = date(2026, 10, 15)
    assert period_bounds("month", d) == ("2026-10-01", None)
    assert period_bounds("alltime", d) == (None, None)
    assert period_bounds("bogus", d) == (None, None)


def test_wrapper_no_tournament_window(db):
    p = _make_player(db, "555-p4wrap", "Wrap")
    db.upsert_central_score({
        "player_id": p, "card_id": "OLD", "game": "hoops",
        "played_at": "1990-01-01", "score": 1,
    })
    tid = db._executemany_return_id(
        "INSERT INTO tournaments (name, type, scope, status, starts_at, ends_at, created_at, updated_at) "
        "VALUES ('Recent', 'solo', 'global', 'active', '2026-10-01', '2026-10-31', 'x', 'x')",
        (),
    )
    db.set_setting("active_global_solo_tournament_id", str(tid))
    assert any(r["card_id"] == "OLD" for r in db.get_leaderboard(limit=50))
    assert not any(
        r["card_id"] == "OLD"
        for r in dashboard.get_leaderboard(db, limit=50, board="individual")
    )


def test_active_global_junk_falls_back_legacy(db):
    db.set_setting("active_global_solo_tournament_id", "not-a-number")
    t = resolve_tournament(db, None, "individual", use_active=True)
    assert t["system_key"] == "legacy_solo"


def test_ties_and_pagination(db):
    p = _make_player(db, "555-p4tie", "Tie")
    ids = []
    for i in range(5):
        db.upsert_central_score({
            "player_id": p, "card_id": f"TIE{i}", "game": "hoops",
            "played_at": f"2026-01-0{i+1}", "score": 100,
        })
        row = db._execute(
            "SELECT id FROM central_scores WHERE card_id = ?", (f"TIE{i}",), fetch="one"
        )
        ids.append(row["id"])
    page1 = tournament_leaderboard(db, board="individual", use_active=False, limit=2, offset=0)
    page2 = tournament_leaderboard(db, board="individual", use_active=False, limit=2, offset=2)
    ordered = sorted(
        [r for r in page1 + page2],
        key=lambda r: (-r["score"], r["id"]),
    )
    assert [r["id"] for r in ordered[:4]] == sorted(ids)[:4]


def test_min_size_clamp_and_team_member_count_fallback(db):
    p = _make_player(db, "555-p4n", "Nrule")
    tsid = db.upsert_central_team_score({
        "session_id": 1, "card_id": "TN", "game": "hoops",
        "played_at": "2026-01-01", "score": 10, "member_count": 3,
        "members_json": "[]", "group_id": 1,
    })
    db.upsert_central_score({
        "player_id": p, "card_id": "SN", "game": "hoops",
        "played_at": "2026-01-01", "score": 5, "team_score_id": tsid,
        "roster_size_at_play": None,
    })
    db.upsert_central_score({
        "player_id": p, "card_id": "S0", "game": "hoops",
        "played_at": "2026-01-02", "score": 5, "roster_size_at_play": 0,
    })
    assert len(db.get_leaderboard(min_size=2)) == 1
    assert len(db.get_leaderboard(min_size=1)) == 2


def test_resolve_tournament_invalid_board(db):
    with pytest.raises(ValueError, match="board must be"):
        resolve_tournament(db, None, "bogus", use_active=False)
