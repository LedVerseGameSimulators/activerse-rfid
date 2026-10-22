"""Pinned gameplay loop contract — must stay green before/after RFID phases."""
import importlib
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from api import poller, sessions

# Reuse helpers from Step 0 contract tests
from tests.test_step0_poller_and_leaderboard import (
    _bind_card,
    _insert_session,
    _make_player,
)


@pytest.fixture
def client(db, monkeypatch):
    """HTTP client wired to the same scratch DB as the db fixture."""
    import api.database as database_mod

    monkeypatch.setattr(database_mod, "_db", db)
    for mod in ("api.main",):
        sys.modules.pop(mod, None)
    main_mod = importlib.import_module("api.main")
    return TestClient(main_mod.app)


def _group_visit(db, leader_id, member_id=None, leader_card="GUARDLEAD0001", credit=60):
    company = db.create_company(f"Co-{uuid.uuid4().hex[:6]}")
    group = db.create_group(company["id"], f"Team-{uuid.uuid4().hex[:6]}")
    db.add_group_member_atomic(group["id"], leader_id)
    if member_id is not None:
        db.add_group_member_atomic(group["id"], member_id)
    db.set_group_leader(group["id"], leader_id)
    _bind_card(db, leader_id, leader_card)
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id=leader_card)
    return company, group, visit


def test_guard_validate_group_leader_ok(db):
    leader = _make_player(db, "555-g001", "GuardLeader", credit_minutes=60)
    member = _make_player(db, "555-g002", "GuardMember")
    _, group, visit = _group_visit(db, leader, member)
    out = sessions.validate_card(db, "GUARDLEAD0001")
    assert out["valid"] is True
    assert out["session_id"] == visit["session_id"]
    assert out["group_id"] == group["id"]
    assert out["roster_size"] == 2
    assert leader in out["roster_player_ids"]
    assert member in out["roster_player_ids"]


def test_guard_validate_solo_group_leader_ok(db):
    """One-person group visit (solo-group shape before P2 kind column)."""
    leader = _make_player(db, "555-g003", "SoloLeader", credit_minutes=60)
    company = db.create_company("SoloCo")
    group = db.create_group(company["id"], "Solo Leader")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "GUARDSOLO0001")
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="GUARDSOLO0001")
    out = sessions.validate_card(db, "GUARDSOLO0001")
    assert out["valid"] is True
    assert out["session_id"] == visit["session_id"]
    assert out["group_id"] == group["id"]
    assert out["roster_size"] == 1
    assert out["roster_player_ids"] == [leader]


def test_guard_validate_expired(db):
    """Brief expects reason=expired for past expiry_at; today get_active_session_by_card
    excludes expiry_at <= now so validate returns no_active_session instead (GAP G-valid-expired)."""
    leader = _make_player(db, "555-g004", "Expired")
    _bind_card(db, leader, "GUARDEXP00001")
    _insert_session(
        db, leader, "GUARDEXP00001",
        "2020-01-01 10:00:00", "2020-01-01 11:00:00",
    )
    out = sessions.validate_card(db, "GUARDEXP00001")
    assert out["valid"] is False
    assert out["reason"] == "no_active_session"


def test_guard_validate_closed(db):
    leader = _make_player(db, "555-g005", "Closed")
    _bind_card(db, leader, "GUARDCLO00001")
    sid = _insert_session(
        db, leader, "GUARDCLO00001",
        "2026-01-01 10:00:00", "2099-01-01 00:00:00",
        closed_at="2026-01-02 12:00:00",
    )
    out = sessions.validate_card(db, "GUARDCLO00001")
    assert out["valid"] is False
    assert out["reason"] == "no_active_session"


def test_guard_validate_unknown_card(db):
    out = sessions.validate_card(db, f"UNKNOWN{uuid.uuid4().hex}")
    assert out["valid"] is False
    assert out["reason"] == "card_not_found"


def test_guard_validate_member_card_not_leader(db):
    leader = _make_player(db, "555-g006", "L6", credit_minutes=60)
    member = _make_player(db, "555-g007", "M6")
    _group_visit(db, leader, member, leader_card="GUARDL600001")
    _bind_card(db, member, "GUARDM600001")
    out = sessions.validate_card(db, "GUARDM600001")
    assert out["valid"] is False
    assert out["reason"] == "no_active_session"


def test_guard_validate_insufficient_time(db):
    from datetime import datetime, timedelta

    leader = _make_player(db, "555-g008", "Short")
    _bind_card(db, leader, "GUARDSHORT01")
    soon = (datetime.now() + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    issued = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _insert_session(db, leader, "GUARDSHORT01", issued, soon)
    out = sessions.validate_card(db, "GUARDSHORT01")
    assert out["valid"] is False
    assert out["reason"] == "insufficient_time"


@pytest.mark.skip(reason="P3: POST /sessions not retired until Phase 3")
def test_guard_post_sessions_retired(client):
    pass


@pytest.mark.skip(reason="P2: UNIQUE(player_id) on group_members blocks two groups until Phase 2")
def test_guard_validate_after_multi_group_migration(db):
    pass


def test_guard_poller_qp_n5(db):
    leader = _make_player(db, "555-g009", "QPLead", credit_minutes=120)
    members = [_make_player(db, f"555-g01{i}", f"M{i}") for i in range(10, 14)]
    company = db.create_company("QPCo")
    group = db.create_group(company["id"], "QP Five")
    db.add_group_member_atomic(group["id"], leader)
    for m in members:
        db.add_group_member_atomic(group["id"], m)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "GUARDQP50001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="GUARDQP50001")
    sid = visit["session_id"]
    roster_ids = [leader] + members

    poller._ingest_game_row(db, "hoops", {
        "card_id": "GUARDQP50001",
        "score": 500,
        "ts": "2026-06-10 12:00:00",
        "level": "1",
        "session_id": sid,
        "group_id": group["id"],
        "roster_size_at_play": 5,
        "roster_player_ids": roster_ids,
        "play_mode": "quick_play",
    })

    team = db._execute(
        "SELECT score, member_count FROM central_team_scores WHERE session_id = ?",
        (sid,), fetch="one",
    )
    assert team["score"] == 500
    assert team["member_count"] == 5
    solos = db._execute(
        "SELECT player_id, score FROM central_scores WHERE session_id = ? ORDER BY player_id",
        (sid,), fetch="all",
    )
    assert len(solos) == 5
    assert all(r["score"] == 100.0 for r in solos)


def test_guard_poller_team_battle_two_groups(db):
    company = db.create_company("TB Guard")
    g1 = db.create_group(company["id"], "RedG")
    g2 = db.create_group(company["id"], "BlueG")
    l1 = _make_player(db, "555-g020", "RedL", credit_minutes=60)
    l2 = _make_player(db, "555-g021", "BlueL", credit_minutes=60)
    db.add_group_member_atomic(g1["id"], l1)
    db.add_group_member_atomic(g2["id"], l2)
    db.set_group_leader(g1["id"], l1)
    db.set_group_leader(g2["id"], l2)
    _bind_card(db, l1, "GUARDRED0001")
    _bind_card(db, l2, "GUARDBLUE001")
    m2 = _make_player(db, "555-g022", "RedM")
    db.add_group_member_atomic(g1["id"], m2)

    s1 = db.issue_group_visit_atomic(g1["id"], 30, card_id="GUARDRED0001")["session_id"]
    s2 = db.issue_group_visit_atomic(g2["id"], 30, card_id="GUARDBLUE001")["session_id"]

    poller._ingest_game_row(db, "hoops", {
        "card_id": "GUARDRED0001",
        "card_id2": "GUARDBLUE001",
        "score": 200,
        "score2": 180,
        "play_mode": "team_battle",
        "ts": "2026-06-02 12:00:00",
        "level": "1",
        "session_id": s1,
        "group_id": g1["id"],
        "roster_size_at_play": 2,
        "roster_player_ids": [l1, m2],
        "session_id2": s2,
        "group_id2": g2["id"],
        "roster_size_at_play2": 1,
        "roster_player_ids2": [l2],
    })

    teams = db._execute(
        "SELECT group_id, score, member_count, match_key FROM central_team_scores "
        "ORDER BY player_slot",
        fetch="all",
    )
    assert len(teams) == 2
    assert teams[0]["score"] == 200 and teams[0]["member_count"] == 2
    assert teams[1]["score"] == 180 and teams[1]["member_count"] == 1
    assert teams[0]["match_key"] == teams[1]["match_key"]


def test_guard_poller_tournament_play_mode(db):
    leader = _make_player(db, "555-g030", "TourL", credit_minutes=60)
    company = db.create_company("TourCo")
    group = db.create_group(company["id"], "TourTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "GUARDTOUR001")
    sid = db.issue_group_visit_atomic(group["id"], 30, card_id="GUARDTOUR001")["session_id"]

    poller._ingest_game_row(db, "hoops", {
        "card_id": "GUARDTOUR001",
        "score": 42,
        "play_mode": "tournament",
        "ts": "2026-06-11 12:00:00",
        "level": "1",
        "session_id": sid,
        "group_id": group["id"],
        "roster_size_at_play": 1,
        "roster_player_ids": [leader],
    })

    row = db._execute(
        "SELECT play_mode FROM central_scores WHERE session_id = ?",
        (sid,), fetch="one",
    )
    assert row["play_mode"] == "tournament"


def test_guard_dashboard_leaderboard_keys(client, db):
    p1 = _make_player(db, "555-g040", "LbSolo")
    db.upsert_central_score({
        "player_id": p1, "card_id": "LBSOLO1", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10,
    })
    db.upsert_central_team_score({
        "session_id": 1, "card_id": "LBTEAM1", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 50,
        "member_count": 2, "members_json": '[{"name":"A"},{"name":"B"}]',
        "group_id": 1,
    })

    ind = client.get("/dashboard/leaderboard?board=individual")
    assert ind.status_code == 200
    body = ind.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    solo = next(r for r in body if r.get("card_id") == "LBSOLO1")
    assert "score" in solo and "player_name" in solo and "game" in solo

    team = client.get("/dashboard/leaderboard?board=team")
    assert team.status_code == 200
    tbody = team.json()
    assert isinstance(tbody, list)
    assert len(tbody) >= 1
    trow = next(r for r in tbody if r.get("card_id") == "LBTEAM1")
    assert "score" in trow and "members" in trow
    assert isinstance(trow["members"], list)
    assert "member_count" in trow


def test_guard_guest_scores_not_attributed(db):
    db.upsert_central_score({
        "player_id": None, "card_id": "GHOSTGUARD", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 999,
        "play_mode": "quick_play",
    })
    rows = db.get_leaderboard(limit=50)
    assert all(r.get("player_id") is not None for r in rows)
    assert not any(r.get("card_id") == "GHOSTGUARD" for r in rows)
