"""Phase 3: retire POST /sessions; Start Visit is the only floor-play entry."""
import importlib
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

from api import sessions
from api.sessions import POST_SESSIONS_RETIRED_DETAIL
from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


@pytest.fixture
def client(db, monkeypatch):
    import api.database as database_mod

    monkeypatch.setattr(database_mod, "_db", db)
    sys.modules.pop("api.main", None)
    main_mod = importlib.import_module("api.main")
    return TestClient(main_mod.app)


def test_post_sessions_returns_410_with_message(client, db):
    pid = _make_player(db, "555-p301", "Legacy", credit_minutes=60)
    _bind_card(db, pid, "CARD-P30101")
    resp = client.post("/sessions", json={"player_id": pid, "duration_min": 45, "notes": "x"})
    assert resp.status_code == 410
    assert resp.json()["detail"] == POST_SESSIONS_RETIRED_DETAIL


def test_solo_group_start_visit_then_validate_unchanged(client, db):
    pid = _make_player(db, "555-p302", "SoloVisit", credit_minutes=60)
    db.ensure_solo_group_for_player(pid)
    solo_gid = db.get_solo_group_id(pid)
    card = "CARD-P30201"
    _bind_card(db, pid, card)
    resp = client.post(
        f"/groups/{solo_gid}/start-visit",
        json={"duration_min": 30, "card_id": card},
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    out = sessions.validate_card(db, card)
    assert out["valid"] is True
    assert out["session_id"] == session_id
    assert out["group_id"] == solo_gid
    assert out["roster_size"] == 1
    assert "members" in out
    assert "roster_player_ids" in out


def test_get_player_does_not_create_solo_group(client, db):
    pid = _make_player(db, "555-p303", "NoSoloYet", credit_minutes=60)
    assert db.get_solo_group_id(pid) is None
    detail = client.get(f"/players/{pid}")
    assert detail.status_code == 200
    assert detail.json()["solo_group_id"] is None
    assert db.get_solo_group_id(pid) is None


def test_ensure_solo_group_then_start_visit(client, db):
    pid = _make_player(db, "555-p303b", "EnsureSolo", credit_minutes=60)
    card = "CARD-P30302"
    _bind_card(db, pid, card)
    ens = client.post(f"/players/{pid}/ensure-solo-group")
    assert ens.status_code == 200
    solo_gid = ens.json()["solo_group_id"]
    assert solo_gid is not None
    resp = client.post(f"/groups/{solo_gid}/start-visit", json={"duration_min": 30})
    assert resp.status_code == 200


def test_start_visit_rejects_leader_without_card(client, db):
    pid = _make_player(db, "555-p306", "NoCardLead", credit_minutes=60)
    db.ensure_solo_group_for_player(pid)
    solo_gid = db.get_solo_group_id(pid)
    bal_before = db.get_credit_balance(pid)
    sessions_before = db._execute(
        "SELECT COUNT(*) AS c FROM player_sessions", fetch="one"
    )["c"]
    ledger_before = db._execute(
        "SELECT COUNT(*) AS c FROM play_time_events", fetch="one"
    )["c"]
    resp = client.post(f"/groups/{solo_gid}/start-visit", json={"duration_min": 30})
    assert resp.status_code == 400
    assert "rfid card bound" in resp.json()["detail"].lower()
    assert db.get_credit_balance(pid) == bal_before
    assert db._execute(
        "SELECT COUNT(*) AS c FROM player_sessions", fetch="one"
    )["c"] == sessions_before
    assert db._execute(
        "SELECT COUNT(*) AS c FROM play_time_events", fetch="one"
    )["c"] == ledger_before


def test_start_visit_accepts_card_id_when_leader_unbound(client, db):
    pid = _make_player(db, "555-p307", "PassCard", credit_minutes=60)
    db.ensure_solo_group_for_player(pid)
    solo_gid = db.get_solo_group_id(pid)
    card = "CARD-P30701"
    resp = client.post(
        f"/groups/{solo_gid}/start-visit",
        json={"duration_min": 30, "card_id": card},
    )
    assert resp.status_code == 200
    assert resp.json()["card_id"] == card


def test_start_visit_duration_max_enforced(client, db):
    pid = _make_player(db, "555-p308", "MaxDur", credit_minutes=60)
    db.ensure_solo_group_for_player(pid)
    solo_gid = db.get_solo_group_id(pid)
    _bind_card(db, pid, "CARD-P30801")
    resp = client.post(
        f"/groups/{solo_gid}/start-visit",
        json={"duration_min": 721},
    )
    assert resp.status_code == 422


def test_start_visit_rejects_archived_group(client, db):
    company = db.create_company(f"Co-{uuid.uuid4().hex[:6]}")
    group = db.create_group(company["id"], "Arch")
    leader = _make_player(db, "555-p304", "ArchLead", credit_minutes=60)
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "CARD-P30401")
    db.archive_group(group["id"])
    resp = client.post(f"/groups/{group['id']}/start-visit", json={"duration_min": 30})
    assert resp.status_code == 400
    assert "archived" in resp.json()["detail"].lower()


def test_start_visit_rejects_busy_player(client, db):
    company = db.create_company(f"Co-{uuid.uuid4().hex[:6]}")
    g1 = db.create_group(company["id"], "Busy1")
    g2 = db.create_group(company["id"], "Busy2")
    leader = _make_player(db, "555-p305", "BusyLead", credit_minutes=120)
    db.add_group_member_atomic(g1["id"], leader)
    db.add_group_member_atomic(g2["id"], leader)
    db.set_group_leader(g1["id"], leader)
    db.set_group_leader(g2["id"], leader)
    card = "CARD-P30501"
    _bind_card(db, leader, card)
    first = client.post(f"/groups/{g1['id']}/start-visit", json={"duration_min": 30})
    assert first.status_code == 200
    second = client.post(f"/groups/{g2['id']}/start-visit", json={"duration_min": 30})
    assert second.status_code == 400
    assert "open session" in second.json()["detail"].lower() or "active" in second.json()["detail"].lower()
