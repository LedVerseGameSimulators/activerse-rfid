import pytest


def _make_player(db, phone, name):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    return db.search_custom_by_field("phone_num", phone)[0]["custom_id"]


def _open_session(db, player_id, group_id=None, company_id=None):
    """Insert a raw open (unexpired, unclosed) session row for guard tests."""
    con = db._conn()
    cur = con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, notes, company_id, group_id) VALUES (?, '', '2026-01-01 00:00:00', "
        "'2099-01-01 00:00:00', 60, '', ?, ?)",
        (player_id, company_id, group_id),
    )
    sid = cur.lastrowid
    con.execute("INSERT INTO session_roster (session_id, player_id) VALUES (?, ?)", (sid, player_id))
    con.commit()
    con.close()
    return sid


# ── add_company_member_atomic ──────────────────────────────────────────────

def test_add_company_member_atomic_joins_company(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-0001", "Alice")
    db.add_company_member_atomic(company["id"], player_id)
    membership = db.get_company_membership(player_id)
    assert membership["company_id"] == company["id"]


def test_add_company_member_atomic_rejects_cross_company(db):
    company_a = db.create_company("Acme")
    company_b = db.create_company("Beta")
    player_id = _make_player(db, "555-0002", "Bob")
    db.add_company_member_atomic(company_a["id"], player_id)
    with pytest.raises(ValueError):
        db.add_company_member_atomic(company_b["id"], player_id)


def test_add_company_member_atomic_idempotent(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-0003", "Carl")
    db.add_company_member_atomic(company["id"], player_id)
    db.add_company_member_atomic(company["id"], player_id)  # same company again, no error
    membership = db.get_company_membership(player_id)
    assert membership["company_id"] == company["id"]


# ── add_group_member_atomic ────────────────────────────────────────────────

def test_add_group_member_atomic_auto_joins_company(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-0010", "Dana")
    db.add_group_member_atomic(group["id"], player_id)
    assert db.get_company_membership(player_id)["company_id"] == company["id"]


def test_add_group_member_atomic_rejects_cross_company(db):
    company_a = db.create_company("Acme")
    company_b = db.create_company("Beta")
    group_b = db.create_group(company_b["id"], "Team B")
    player_id = _make_player(db, "555-0011", "Erin")
    db.add_company_member_atomic(company_a["id"], player_id)
    with pytest.raises(ValueError):
        db.add_group_member_atomic(group_b["id"], player_id)


def test_add_group_member_atomic_rejects_second_group(db):
    company = db.create_company("Acme")
    group_1 = db.create_group(company["id"], "Team A")
    group_2 = db.create_group(company["id"], "Team B")
    player_id = _make_player(db, "555-0012", "Finn")
    db.add_group_member_atomic(group_1["id"], player_id)
    with pytest.raises(ValueError):
        db.add_group_member_atomic(group_2["id"], player_id)


def test_add_group_member_atomic_walk_in_group_skips_company_checks(db):
    group = db.create_group(None, "Birthday Party Team")
    player_id = _make_player(db, "555-0013", "Gary")
    db.add_group_member_atomic(group["id"], player_id)
    assert db.get_company_membership(player_id) is None
    members = db.get_group_members(group["id"])
    assert any(m["player_id"] == player_id for m in members)


# ── transfer_group_member_atomic ───────────────────────────────────────────

def test_transfer_group_member_atomic_moves_between_groups(db):
    company = db.create_company("Acme")
    group_1 = db.create_group(company["id"], "Team A")
    group_2 = db.create_group(company["id"], "Team B")
    player_id = _make_player(db, "555-0020", "Hana")
    db.add_group_member_atomic(group_1["id"], player_id)

    db.transfer_group_member_atomic(group_2["id"], player_id)

    assert not any(m["player_id"] == player_id for m in db.get_group_members(group_1["id"]))
    assert any(m["player_id"] == player_id for m in db.get_group_members(group_2["id"]))


def test_transfer_group_member_atomic_rejects_leader(db):
    company = db.create_company("Acme")
    group_1 = db.create_group(company["id"], "Team A")
    group_2 = db.create_group(company["id"], "Team B")
    player_id = _make_player(db, "555-0021", "Ivy")
    db.add_group_member_atomic(group_1["id"], player_id)
    db.set_group_leader(group_1["id"], player_id)

    with pytest.raises(ValueError):
        db.transfer_group_member_atomic(group_2["id"], player_id)


def test_transfer_group_member_atomic_rejects_cross_company(db):
    company_a = db.create_company("Acme")
    company_b = db.create_company("Beta")
    group_1 = db.create_group(company_a["id"], "Team A")
    group_2 = db.create_group(company_b["id"], "Team B")
    player_id = _make_player(db, "555-0022", "Jill")
    db.add_group_member_atomic(group_1["id"], player_id)

    with pytest.raises(ValueError):
        db.transfer_group_member_atomic(group_2["id"], player_id)


def test_transfer_group_member_atomic_walk_in_unrestricted(db):
    walk_in = db.create_group(None, "Birthday Party Team")
    company = db.create_company("Acme")
    corp_group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-0023", "Kim")
    db.add_group_member_atomic(walk_in["id"], player_id)

    db.transfer_group_member_atomic(corp_group["id"], player_id)

    assert any(m["player_id"] == player_id for m in db.get_group_members(corp_group["id"]))
    assert db.get_company_membership(player_id)["company_id"] == company["id"]


# ── delete_group / delete_company guards ───────────────────────────────────

def test_delete_group_blocked_by_open_session(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-0030", "Liam")
    db.add_group_member_atomic(group["id"], player_id)
    _open_session(db, player_id, group_id=group["id"])

    with pytest.raises(ValueError):
        db.delete_group(group["id"])


def test_delete_group_keeps_company_members(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-0031", "Mona")
    db.add_group_member_atomic(group["id"], player_id)

    db.delete_group(group["id"])

    assert db.get_company_membership(player_id)["company_id"] == company["id"]


def test_delete_company_blocked_by_open_session(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-0032", "Nia")
    db.add_company_member_atomic(company["id"], player_id)
    _open_session(db, player_id, company_id=company["id"])

    with pytest.raises(ValueError):
        db.delete_company(company["id"])


def test_delete_company_removes_company_members(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-0033", "Omar")
    db.add_company_member_atomic(company["id"], player_id)

    db.delete_company(company["id"])

    assert db.get_company_membership(player_id) is None


# ── remove_company_member (leave company) ──────────────────────────────────

def test_remove_company_member_blocked_by_open_session(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-0040", "Pia")
    db.add_company_member_atomic(company["id"], player_id)
    _open_session(db, player_id, company_id=company["id"])

    with pytest.raises(ValueError):
        db.remove_company_member(company["id"], player_id)


def test_remove_company_member_auto_removes_from_group(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-0041", "Quinn")
    db.add_group_member_atomic(group["id"], player_id)

    db.remove_company_member(company["id"], player_id)

    assert db.get_company_membership(player_id) is None
    assert not any(m["player_id"] == player_id for m in db.get_group_members(group["id"]))
