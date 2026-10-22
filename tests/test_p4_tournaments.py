"""P4a tournament API — CRUD, validation, envelope leaderboard."""
import importlib
import sys

import pytest
from fastapi.testclient import TestClient

from tests.test_step0_poller_and_leaderboard import _make_player


@pytest.fixture
def client(db, monkeypatch):
    import api.database as database_mod

    monkeypatch.setattr(database_mod, "_db", db)
    sys.modules.pop("api.main", None)
    main_mod = importlib.import_module("api.main")
    return TestClient(main_mod.app)


def test_tournaments_active_returns_legacy(client):
    r = client.get("/tournaments/active")
    assert r.status_code == 200
    body = r.json()
    assert body["solo"]["system_key"] == "legacy_solo"
    assert body["team"]["system_key"] == "legacy_team"
    assert body["solo"]["is_active_global"] is True


def test_create_and_list_tournament(client, db):
    r = client.post("/tournaments", json={
        "name": "October Solo",
        "type": "solo",
        "scope": "global",
        "starts_at": "2026-10-01",
        "ends_at": "2026-10-31",
    })
    assert r.status_code == 200
    tid = r.json()["id"]
    listed = client.get("/tournaments?type=solo").json()
    assert any(t["id"] == tid for t in listed)


def test_validation_name_and_dates(client):
    assert client.post("/tournaments", json={
        "name": "", "type": "solo", "scope": "global",
    }).status_code == 422
    assert client.post("/tournaments", json={
        "name": "X", "type": "solo", "scope": "global",
        "starts_at": "2026-10-31", "ends_at": "2026-10-01",
    }).status_code == 422
    assert client.post("/tournaments", json={
        "name": "X", "type": "solo", "scope": "global",
        "starts_at": "2026-10-01T00:00:00",
    }).status_code == 422


def test_strict_tournament_dates(client):
    base = {"name": "X", "type": "solo", "scope": "global"}
    for bad in ("20260101", "2026-W01-1", "2026-1-1", "2026-02-30"):
        assert client.post("/tournaments", json={**base, "starts_at": bad}).status_code == 422
    ok = client.post("/tournaments", json={
        **base, "starts_at": "2026-10-01", "ends_at": "2026-10-31",
    })
    assert ok.status_code == 200
    assert ok.json()["starts_at"] == "2026-10-01"


def test_company_scope_requires_company(client, db):
    r = client.post("/tournaments", json={
        "name": "Co cup", "type": "team", "scope": "company",
    })
    assert r.status_code == 422
    cid = db.create_company("P4 Co")["id"]
    r = client.post("/tournaments", json={
        "name": "Co cup", "type": "team", "scope": "company", "company_id": cid,
    })
    assert r.status_code == 200


def test_system_row_delete_and_archive_blocked(client):
    legacy = client.get("/tournaments/active").json()["solo"]["id"]
    assert client.delete(f"/tournaments/{legacy}").status_code == 409
    assert client.put(f"/tournaments/{legacy}", json={"status": "archived"}).status_code == 409


def test_activate_global_switches_dashboard(client, db):
    p = _make_player(db, "555-p4act", "Act")
    db.upsert_central_score({
        "player_id": p, "card_id": "ACTOLD", "game": "hoops",
        "played_at": "1990-01-01", "score": 1,
    })
    db.upsert_central_score({
        "player_id": p, "card_id": "ACTNEW", "game": "hoops",
        "played_at": "2026-10-15", "score": 2,
    })
    cr = client.post("/tournaments", json={
        "name": "Oct only", "type": "solo", "scope": "global",
        "starts_at": "2026-10-01", "ends_at": "2026-10-31",
    })
    tid = cr.json()["id"]
    client.post(f"/tournaments/{tid}/activate-global", json={"which": "solo"})
    lb = client.get("/dashboard/leaderboard?board=individual&limit=50").json()
    cards = {r["card_id"] for r in lb}
    assert "ACTNEW" in cards
    assert "ACTOLD" not in cards


def test_dashboard_shape_compat(client, db):
    p = _make_player(db, "555-p4sh", "Shape")
    db.upsert_central_score({
        "player_id": p, "card_id": "SHSOLO", "game": "hoops",
        "played_at": "2026-01-01", "score": 10, "final_score": 10,
    })
    db.upsert_central_team_score({
        "session_id": 1, "card_id": "SHTEAM", "game": "hoops",
        "played_at": "2026-01-01", "score": 50, "member_count": 2,
        "members_json": '[{"name":"A"}]', "group_id": 3,
    })
    ind = client.get("/dashboard/leaderboard?board=individual").json()
    assert isinstance(ind, list)
    solo = next(r for r in ind if r.get("card_id") == "SHSOLO")
    for k in ("id", "player_id", "card_id", "game", "level", "score", "final_score", "played_at", "player_name"):
        assert k in solo
    team = client.get("/dashboard/leaderboard?board=team").json()
    trow = next(r for r in team if r.get("card_id") == "SHTEAM")
    for k in ("score", "members", "member_count", "player_name", "card_id"):
        assert k in trow


def test_envelope_leaderboard(client, db):
    p = _make_player(db, "555-p4env", "Env")
    db.upsert_central_score({
        "player_id": p, "card_id": "ENV1", "game": "hoops",
        "played_at": "2026-10-10", "score": 5,
    })
    cr = client.post("/tournaments", json={
        "name": "Oct", "type": "solo", "scope": "global",
        "starts_at": "2026-10-01", "ends_at": "2026-10-31",
    })
    tid = cr.json()["id"]
    r = client.get(f"/tournaments/{tid}/leaderboard?limit=10")
    assert r.status_code == 200
    body = r.json()
    for k in ("tournament", "board", "filters", "window", "total", "limit", "offset", "rows"):
        assert k in body
    assert body["total"] >= 1
    assert body["rows"][0]["rank"] == 1


def test_envelope_play_mode_strict(client, db):
    cr = client.post("/tournaments", json={
        "name": "T", "type": "solo", "scope": "global",
    })
    tid = cr.json()["id"]
    assert client.get(
        f"/tournaments/{tid}/leaderboard?play_mode=invalid"
    ).status_code == 422
    assert client.get(
        "/dashboard/leaderboard?play_mode=invalid"
    ).status_code == 200


def test_wrong_board_tournament_id(client, db):
    cr = client.post("/tournaments", json={
        "name": "Team T", "type": "team", "scope": "global",
    })
    tid = cr.json()["id"]
    r = client.get(f"/dashboard/leaderboard?board=individual&tournament_id={tid}")
    assert r.status_code == 400


def test_active_global_archive_and_draft_blocked(client, db):
    cr = client.post("/tournaments", json={
        "name": "Custom global", "type": "solo", "scope": "global",
        "starts_at": "2026-01-01", "ends_at": "2026-12-31",
    })
    tid = cr.json()["id"]
    client.post(f"/tournaments/{tid}/activate-global", json={"which": "solo"})
    assert client.put(f"/tournaments/{tid}", json={"status": "archived"}).status_code == 409
    assert client.put(f"/tournaments/{tid}", json={"status": "draft"}).status_code == 409
    legacy_id = next(
        t["id"]
        for t in client.get("/tournaments?type=solo").json()
        if t.get("system_key") == "legacy_solo"
    )
    client.post(f"/tournaments/{legacy_id}/activate-global", json={"which": "solo"})
    assert client.put(f"/tournaments/{tid}", json={"status": "archived"}).status_code == 200


def test_draft_active_global_falls_back_to_legacy(client, db):
    cr = client.post("/tournaments", json={
        "name": "Draft me", "type": "solo", "scope": "global", "status": "draft",
    })
    tid = cr.json()["id"]
    db.set_setting("active_global_solo_tournament_id", str(tid))
    active = client.get("/tournaments/active").json()["solo"]
    assert active["system_key"] == "legacy_solo"


def test_entrant_count_window_and_company_scope(client, db):
    p1 = _make_player(db, "555-ec1", "E1")
    p2 = _make_player(db, "555-ec2", "E2")
    p3 = _make_player(db, "555-ec3", "E3")
    for card, played_at in (("ECIN1", "2026-10-05"), ("ECIN2", "2026-10-10"), ("ECOUT", "2026-11-05")):
        db.upsert_central_score({
            "player_id": p1 if card != "ECIN2" else p2,
            "card_id": card, "game": "hoops", "played_at": played_at, "score": 1,
        })
    cr = client.post("/tournaments", json={
        "name": "Oct entrants", "type": "solo", "scope": "global",
        "starts_at": "2026-10-01", "ends_at": "2026-10-31",
    })
    tid = cr.json()["id"]
    detail = client.get(f"/tournaments/{tid}").json()
    assert detail["play_count"] == 2
    assert detail["entrant_count"] == 2

    cid = db.create_company("Entrant Co")["id"]
    db.upsert_central_score({
        "player_id": p3, "card_id": "ECCO", "game": "hoops",
        "played_at": "2026-10-15", "score": 1, "company_id": cid,
    })
    db.upsert_central_score({
        "player_id": p1, "card_id": "ECOTHER", "game": "hoops",
        "played_at": "2026-10-15", "score": 1, "company_id": cid + 99,
    })
    tco = client.post("/tournaments", json={
        "name": "Co cup", "type": "solo", "scope": "company", "company_id": cid,
        "starts_at": "2026-10-01", "ends_at": "2026-10-31",
    }).json()["id"]
    co_detail = client.get(f"/tournaments/{tco}").json()
    assert co_detail["play_count"] == 1
    assert co_detail["entrant_count"] == 1


def test_dashboard_invalid_board_and_param_clamp(client, db):
    assert client.get("/dashboard/leaderboard?board=invalid").status_code == 422
    assert client.get("/dashboard/leaderboard?limit=0").status_code == 200
    assert client.get("/dashboard/leaderboard?min_size=-1&max_size=-2").status_code == 200
