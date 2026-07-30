import pytest
from fastapi import HTTPException

from api import groups, companies


def _make_player(db, phone, name, credit_minutes=0):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    player_id = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    if credit_minutes:
        db.add_credit(player_id, credit_minutes, 0)
    return player_id


# ── groups.create_group: optional company_id ───────────────────────────────

def test_create_group_walk_in_no_company(db):
    group = groups.create_group(db, None, "Birthday Party Team")
    assert group["company_id"] is None


def test_create_group_corporate_still_validates_company_exists(db):
    with pytest.raises(HTTPException) as exc:
        groups.create_group(db, 9999, "Team A")
    assert exc.value.status_code == 404


# ── groups.add_member: atomic + HTTPException mapping ──────────────────────

def test_add_member_rejects_cross_company_as_400(db):
    company_a = companies.create_company(db, "Acme")
    company_b = companies.create_company(db, "Beta")
    group_b = groups.create_group(db, company_b["id"], "Team B")
    player_id = _make_player(db, "555-5001", "Alice")
    db.add_company_member_atomic(company_a["id"], player_id)

    with pytest.raises(HTTPException) as exc:
        groups.add_member(db, group_b["id"], player_id=player_id)
    assert exc.value.status_code == 400


def test_add_member_walk_in_group_succeeds(db):
    group = groups.create_group(db, None, "Birthday Party Team")
    player_id = _make_player(db, "555-5002", "Bob")
    result = groups.add_member(db, group["id"], player_id=player_id)
    assert any(m["player_id"] == player_id for m in result["members"])


# ── groups.delete_group: open-session guard ────────────────────────────────

def test_delete_group_blocked_returns_400(db):
    company = companies.create_company(db, "Acme")
    group = groups.create_group(db, company["id"], "Team A")
    player_id = _make_player(db, "555-5003", "Carl")
    groups.add_member(db, group["id"], player_id=player_id)
    con = db._conn()
    cur = con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, notes, group_id) VALUES (?, '', '2026-01-01 00:00:00', "
        "'2099-01-01 00:00:00', 60, '', ?)",
        (player_id, group["id"]),
    )
    con.commit()
    con.close()

    with pytest.raises(HTTPException) as exc:
        groups.delete_group(db, group["id"])
    assert exc.value.status_code == 400


# ── groups.start_visit: rewired to issue_group_visit_atomic ────────────────

def test_start_visit_success_shape(db):
    company = companies.create_company(db, "Acme")
    group = groups.create_group(db, company["id"], "Team A")
    leader_id = _make_player(db, "555-5004", "Leader", credit_minutes=60)
    member_id = _make_player(db, "555-5005", "Member")
    groups.add_member(db, group["id"], player_id=leader_id)
    groups.add_member(db, group["id"], player_id=member_id)
    groups.set_leader(db, group["id"], leader_id)

    result = groups.start_visit(db, group["id"], 30, card_id="CARDSTART1")

    assert result["company_id"] == company["id"]
    assert result["group_id"] == group["id"]
    assert {r["player_id"] for r in result["roster"]} == {leader_id, member_id}


def test_start_visit_no_leader_returns_400(db):
    company = companies.create_company(db, "Acme")
    group = groups.create_group(db, company["id"], "Team A")
    member_id = _make_player(db, "555-5006", "Member")
    groups.add_member(db, group["id"], player_id=member_id)

    with pytest.raises(HTTPException) as exc:
        groups.start_visit(db, group["id"], 30)
    assert exc.value.status_code == 400


def test_start_visit_walk_in_group(db):
    group = groups.create_group(db, None, "Birthday Party Team")
    leader_id = _make_player(db, "555-5007", "Leader", credit_minutes=60)
    groups.add_member(db, group["id"], player_id=leader_id)
    groups.set_leader(db, group["id"], leader_id)

    result = groups.start_visit(db, group["id"], 30)
    assert result["company_id"] is None
    assert result["group_id"] == group["id"]


# ── groups.transfer_member: new ─────────────────────────────────────────────

def test_transfer_member_moves_between_groups(db):
    company = companies.create_company(db, "Acme")
    group_1 = groups.create_group(db, company["id"], "Team A")
    group_2 = groups.create_group(db, company["id"], "Team B")
    player_id = _make_player(db, "555-5008", "Dana")
    groups.add_member(db, group_1["id"], player_id=player_id)

    result = groups.transfer_member(db, group_2["id"], player_id)

    assert any(m["player_id"] == player_id for m in result["members"])
    detail_1 = groups.get_group(db, group_1["id"])
    assert not any(m["player_id"] == player_id for m in detail_1["members"])


def test_transfer_member_leader_returns_400(db):
    company = companies.create_company(db, "Acme")
    group_1 = groups.create_group(db, company["id"], "Team A")
    group_2 = groups.create_group(db, company["id"], "Team B")
    player_id = _make_player(db, "555-5009", "Erin")
    groups.add_member(db, group_1["id"], player_id=player_id)
    groups.set_leader(db, group_1["id"], player_id)

    with pytest.raises(HTTPException) as exc:
        groups.transfer_member(db, group_2["id"], player_id)
    assert exc.value.status_code == 400


# ── companies.delete_company: open-session guard ───────────────────────────

def test_delete_company_blocked_returns_400(db):
    company = companies.create_company(db, "Acme")
    player_id = _make_player(db, "555-5010", "Finn")
    db.add_company_member_atomic(company["id"], player_id)
    con = db._conn()
    con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, notes, company_id) VALUES (?, '', '2026-01-01 00:00:00', "
        "'2099-01-01 00:00:00', 60, '', ?)",
        (player_id, company["id"]),
    )
    con.commit()
    con.close()

    with pytest.raises(HTTPException) as exc:
        companies.delete_company(db, company["id"])
    assert exc.value.status_code == 400


# ── companies.list_members / leave_company: new ────────────────────────────

def test_list_members_returns_company_roster(db):
    company = companies.create_company(db, "Acme")
    player_id = _make_player(db, "555-5011", "Gary")
    db.add_company_member_atomic(company["id"], player_id)

    members = companies.list_members(db, company["id"])
    assert any(m["player_id"] == player_id for m in members)


def test_leave_company_removes_membership(db):
    company = companies.create_company(db, "Acme")
    player_id = _make_player(db, "555-5012", "Hana")
    db.add_company_member_atomic(company["id"], player_id)

    companies.leave_company(db, company["id"], player_id)

    assert db.get_company_membership(player_id) is None


def test_leave_company_blocked_by_open_session_returns_400(db):
    company = companies.create_company(db, "Acme")
    player_id = _make_player(db, "555-5013", "Ivy")
    db.add_company_member_atomic(company["id"], player_id)
    con = db._conn()
    cur = con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, notes, company_id) VALUES (?, '', '2026-01-01 00:00:00', "
        "'2099-01-01 00:00:00', 60, '', ?)",
        (player_id, company["id"]),
    )
    con.execute(
        "INSERT INTO session_roster (session_id, player_id) VALUES (?, ?)",
        (cur.lastrowid, player_id),
    )
    con.commit()
    con.close()

    with pytest.raises(HTTPException) as exc:
        companies.leave_company(db, company["id"], player_id)
    assert exc.value.status_code == 400
