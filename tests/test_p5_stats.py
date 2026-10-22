"""P5a read-only stat sheet APIs."""
import importlib
import sys
import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api import poller, sessions
from tests.test_step0_poller_and_leaderboard import (
    _bind_card,
    _insert_session,
    _make_player,
)


@pytest.fixture
def client(db, monkeypatch):
    import api.database as database_mod

    monkeypatch.setattr(database_mod, "_db", db)
    sys.modules.pop("api.main", None)
    main_mod = importlib.import_module("api.main")
    return TestClient(main_mod.app)


def _seed_p5_dataset(db):
    """Company A, team of 3, solo groups, two visits, battle, guest, archived group."""
    company = db.create_company("P5 Acme")
    cid = company["id"]

    leader = _make_player(db, "555-p5-01", "Alice", credit_minutes=120)
    bob = _make_player(db, "555-p5-02", "Bob", credit_minutes=60)
    carol = _make_player(db, "555-p5-03", "Carol", credit_minutes=60)
    for pid in (leader, bob, carol):
        db.ensure_solo_group_for_player(pid)

    db._execute(
        "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
        "VALUES (?, ?, datetime('now'))",
        (cid, leader),
    )
    db._execute(
        "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
        "VALUES (?, ?, datetime('now'))",
        (cid, bob),
    )
    db._execute(
        "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
        "VALUES (?, ?, datetime('now'))",
        (cid, carol),
    )

    team = db.create_group(cid, "Acme Blue", leader_player_id=leader)
    db.set_group_leader(team["id"], leader)

    archived = db.create_group(cid, "Old Team", leader_player_id=leader)
    db.archive_group(archived["id"])

    _bind_card(db, leader, "P5LEAD00001")
    _bind_card(db, bob, "P5BOB000001")

    visit1 = db.issue_group_visit_atomic(team["id"], 60, card_id="P5LEAD00001")
    sid1 = visit1["session_id"]
    db.add_group_member_atomic(team["id"], bob)
    db.add_roster_member_atomic(sid1, bob)

    db.upsert_central_team_score({
        "session_id": sid1,
        "card_id": "P5LEAD00001",
        "game": "hoops",
        "score": 300.0,
        "played_at": "2026-10-10T12:00:00",
        "company_id": cid,
        "group_id": team["id"],
        "play_mode": "quick_play",
        "roster_size_at_play": 2,
        "member_count": 2,
    })
    tid = db._execute(
        "SELECT id FROM central_team_scores WHERE card_id = 'P5LEAD00001'",
        fetch="one",
    )["id"]
    db.upsert_central_score({
        "player_id": leader,
        "session_id": sid1,
        "team_score_id": tid,
        "card_id": "P5LEAD00001",
        "game": "hoops",
        "score": 150.0,
        "played_at": "2026-10-10T12:00:00",
        "company_id": cid,
        "group_id": team["id"],
        "play_mode": "quick_play",
        "roster_size_at_play": 2,
    })
    db.upsert_central_score({
        "player_id": bob,
        "session_id": sid1,
        "team_score_id": tid,
        "card_id": "P5LEAD00001",
        "game": "hoops",
        "score": 150.0,
        "played_at": "2026-10-10T12:00:00",
        "company_id": cid,
        "group_id": team["id"],
        "play_mode": "quick_play",
        "roster_size_at_play": 2,
    })
    db.upsert_central_score({
        "player_id": None,
        "card_id": "GUESTCARD01",
        "game": "hoops",
        "score": 99.0,
        "played_at": "2026-10-10 13:00:00",
        "company_id": cid,
    })

    db.upsert_central_team_score({
        "session_id": None,
        "card_id": "P5LASER0001",
        "game": "laser",
        "score": 200.0,
        "played_at": "2026-09-15 10:00:00",
        "company_id": None,
        "group_id": team["id"],
        "play_mode": "tournament",
        "member_count": 2,
    })

    _bind_card(db, carol, "P5CAROL0001")
    g2 = db.create_group(cid, "Acme Red", leader_player_id=carol)
    db.add_group_member_atomic(g2["id"], carol)
    db.set_group_leader(g2["id"], carol)
    s2 = db.issue_group_visit_atomic(g2["id"], 30, card_id="P5CAROL0001")

    red = g2["id"]
    blue = team["id"]
    poller._ingest_game_row(db, "hoops", {
        "card_id": "P5LEAD00001",
        "card_id2": "P5CAROL0001",
        "score": 220,
        "score2": 200,
        "play_mode": "team_battle",
        "ts": "2026-10-11 14:00:00",
        "level": "1",
        "session_id": sid1,
        "group_id": blue,
        "roster_size_at_play": 2,
        "roster_player_ids": [leader, bob],
        "session_id2": s2["session_id"],
        "group_id2": red,
        "roster_size_at_play2": 1,
        "roster_player_ids2": [carol],
    })

    db.adjust_session(
        sid1, 15, "bonus time", "staff",
        adjustment_mode="free_clock",
        balance_delta_min=0,
    )

    return {
        "company_id": cid,
        "team_id": team["id"],
        "archived_id": archived["id"],
        "leader": leader,
        "bob": bob,
        "session_id": sid1,
    }


@pytest.fixture
def p5(db):
    return _seed_p5_dataset(db)


def test_stats_unknown_ids_404(client):
    assert client.get("/stats/player/99999").status_code == 404
    assert client.get("/stats/session/99999").status_code == 404
    assert client.get("/stats/group/99999").status_code == 404
    assert client.get("/stats/company/99999").status_code == 404
    assert client.get("/stats/game/not_a_game").status_code == 404
    assert client.get("/stats/tournament/99999").status_code == 404


def test_stats_bad_date_422(client, p5):
    pid = p5["leader"]
    assert client.get(f"/stats/player/{pid}?date_from=20260101").status_code == 422
    assert client.get(f"/stats/player/{pid}?play_mode=invalid").status_code == 422


def test_player_stats_numbers(client, p5):
    pid = p5["leader"]
    r = client.get(f"/stats/player/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert "player" in body and "plays" in body and "play_time" in body
    assert body["plays"]["count"] == 2
    assert body["plays"]["best"] == 150.0
    assert sum(g["plays"] for g in body["plays"]["by_game"]) == 2
    earned = body["play_time"]["earned_min"]
    assert earned >= 60.0
    assert "adjust_net_min" in body["play_time"]
    assert body["play_time"]["refund_min"] >= 0


def test_guest_excluded_from_player_stats(client, p5):
    r = client.get(f"/stats/player/{p5['leader']}")
    assert r.status_code == 200
    assert r.json()["plays"]["count"] == 2


def test_session_stats_roster_and_plays(client, p5):
    sid = p5["session_id"]
    r = client.get(f"/stats/session/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["roster"]) >= 2
    alice = next(m for m in body["roster"] if m["player_id"] == p5["leader"])
    assert alice["earned_min"] == 60.0
    bob = next(m for m in body["roster"] if m["player_id"] == p5["bob"])
    assert bob["earned_min"] > 0
    assert bob["joined_via"] == "roster_join"
    assert len(body["adjustments"]) >= 1
    assert body["adjustments"][0]["adjustment_mode"] == "free_clock"
    member_total = sum(m["total_share"] for m in body["plays"]["by_member"])
    team_total = body["plays"]["total_team_score"]
    assert abs(member_total - team_total) < 0.02


def test_group_stats_archived_readable(client, p5):
    r = client.get(f"/stats/group/{p5['archived_id']}")
    assert r.status_code == 200
    assert r.json()["group"]["archived_at"] is not None


def test_group_team_battle_head_to_head(client, p5):
    r = client.get(f"/stats/group/{p5['team_id']}")
    body = r.json()
    assert body["team_plays"]["matches"] >= 1
    h2h = body["team_plays"]["head_to_head"]
    assert h2h["wins"] + h2h["losses"] + h2h["draws"] >= 1


def test_company_stamped_only(client, p5, db):
    r = client.get(f"/stats/company/{p5['company_id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["plays"]["team_plays"] >= 3
    assert body["plays"]["shares"] >= 2
    unstamped = db._execute(
        "SELECT COUNT(*) AS c FROM central_team_scores WHERE company_id IS NULL AND group_id = ?",
        (p5["team_id"],),
        fetch="one",
    )["c"]
    assert unstamped >= 1


def test_game_stats_matches_and_dates(client, p5):
    r = client.get("/stats/game/hoops?date_from=2026-10-01&date_to=2026-10-31")
    assert r.status_code == 200
    body = r.json()
    assert body["volume"]["matches"] >= 1
    assert body["game"] == "hoops"


def test_tournament_stats_consistent_with_leaderboard(client, p5, db):
    cr = client.post("/tournaments", json={
        "name": "P5 Oct Solo",
        "type": "solo",
        "scope": "global",
        "starts_at": "2026-10-01",
        "ends_at": "2026-10-31",
    })
    tid = cr.json()["id"]
    lb = client.get(f"/tournaments/{tid}/leaderboard")
    stats = client.get(f"/stats/tournament/{tid}")
    assert stats.status_code == 200
    assert stats.json()["totals"]["plays"] == lb.json()["total"]


def test_date_window_filters(client, p5):
    pid = p5["leader"]
    r = client.get(f"/stats/player/{pid}?date_from=2026-10-01&date_to=2026-10-31")
    assert r.status_code == 200
    assert r.json()["plays"]["count"] == 2
    r2 = client.get(f"/stats/player/{pid}?date_from=2026-09-01&date_to=2026-09-30")
    assert r2.json()["plays"]["count"] == 0


def test_stats_read_only_no_db_writes(client, p5, db):
    tables = [
        "central_scores", "central_team_scores", "play_time_events",
        "player_sessions", "session_roster", "custom_info",
    ]
    before = {t: db._execute(f"SELECT COUNT(*) AS c FROM {t}", fetch="one")["c"] for t in tables}
    client.get(f"/stats/player/{p5['leader']}")
    client.get(f"/stats/session/{p5['session_id']}")
    client.get(f"/stats/group/{p5['team_id']}")
    client.get(f"/stats/company/{p5['company_id']}")
    client.get("/stats/game/hoops")
    client.get("/stats/tournament/1")
    after = {t: db._execute(f"SELECT COUNT(*) AS c FROM {t}", fetch="one")["c"] for t in tables}
    assert before == after


def test_per_day_mixed_timestamp_formats(client, db):
    db.upsert_central_team_score({
        "card_id": "FMT1", "game": "hoops", "score": 10,
        "played_at": "2026-10-31T23:59:59", "session_id": 1, "group_id": 1,
    })
    db.upsert_central_team_score({
        "card_id": "FMT2", "game": "hoops", "score": 11,
        "played_at": "2026-10-31 12:00:00", "session_id": 1, "group_id": 1,
    })
    r = client.get("/stats/game/hoops?date_from=2026-10-31&date_to=2026-10-31")
    assert r.status_code == 200
    vol = r.json()["volume"]["team_plays"]
    assert vol >= 2
