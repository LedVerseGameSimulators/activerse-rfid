import pytest


def _make_player(db, phone, name, credit_minutes=0):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    player_id = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    if credit_minutes:
        db.add_credit(player_id, credit_minutes, 0)
    return player_id


def _session_count(db):
    return db._execute("SELECT COUNT(*) c FROM player_sessions", fetch="one")["c"]


def _raw_open_session(db, player_id):
    """Insert a raw open session bypassing issue_session_atomic's own-group
    check — simulates a pre-existing session from before the player joined a team."""
    con = db._conn()
    cur = con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, notes) VALUES (?, 'RAWCARD', '2026-01-01 00:00:00', "
        "'2099-01-01 00:00:00', 15, '')",
        (player_id,),
    )
    sid = cur.lastrowid
    con.execute("INSERT INTO session_roster (session_id, player_id) VALUES (?, ?)", (sid, player_id))
    con.commit()
    con.close()
    return sid


def test_issue_group_visit_atomic_missing_leader_raises(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    member_id = _make_player(db, "555-2001", "Alice")
    db.add_group_member_atomic(group["id"], member_id)

    with pytest.raises(ValueError, match="leader"):
        db.issue_group_visit_atomic(group["id"], 30)
    assert _session_count(db) == 0


def test_issue_group_visit_atomic_empty_group_raises(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    with pytest.raises(ValueError):
        db.issue_group_visit_atomic(group["id"], 30)


def test_issue_group_visit_atomic_success_stamps_company_and_group(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    leader_id = _make_player(db, "555-2002", "Leader", credit_minutes=60)
    member_id = _make_player(db, "555-2003", "Member")
    db.add_group_member_atomic(group["id"], leader_id)
    db.add_group_member_atomic(group["id"], member_id)
    db.set_group_leader(group["id"], leader_id)

    result = db.issue_group_visit_atomic(group["id"], 30, card_id="CARDLEAD01")

    session = db._execute(
        "SELECT * FROM player_sessions WHERE id = ?", (result["session_id"],), fetch="one"
    )
    assert session["company_id"] == company["id"]
    assert session["group_id"] == group["id"]
    roster_ids = {r["player_id"] for r in db._execute(
        "SELECT player_id FROM session_roster WHERE session_id = ?",
        (result["session_id"],), fetch="all")}
    assert roster_ids == {leader_id, member_id}
    assert db.get_credit_balance(leader_id) == 30


def test_issue_group_visit_atomic_walk_in_group_has_no_company(db):
    group = db.create_group(None, "Birthday Party Team")
    leader_id = _make_player(db, "555-2004", "Leader", credit_minutes=60)
    db.add_group_member_atomic(group["id"], leader_id)
    db.set_group_leader(group["id"], leader_id)

    result = db.issue_group_visit_atomic(group["id"], 30)

    session = db._execute(
        "SELECT * FROM player_sessions WHERE id = ?", (result["session_id"],), fetch="one"
    )
    assert session["company_id"] is None
    assert session["group_id"] == group["id"]


def test_issue_group_visit_atomic_insufficient_credit_writes_nothing(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    leader_id = _make_player(db, "555-2005", "Leader", credit_minutes=5)
    db.add_group_member_atomic(group["id"], leader_id)
    db.set_group_leader(group["id"], leader_id)

    with pytest.raises(ValueError):
        db.issue_group_visit_atomic(group["id"], 30)
    assert _session_count(db) == 0
    assert db.get_credit_balance(leader_id) == 5


def test_issue_group_visit_atomic_member_already_busy_blocks_whole_visit(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    leader_id = _make_player(db, "555-2006", "Leader", credit_minutes=60)
    member_id = _make_player(db, "555-2007", "Member", credit_minutes=60)
    db.add_group_member_atomic(group["id"], leader_id)
    db.add_group_member_atomic(group["id"], member_id)
    db.set_group_leader(group["id"], leader_id)

    # member already has an unrelated open solo session (pre-dating team membership)
    _raw_open_session(db, member_id)

    with pytest.raises(ValueError):
        db.issue_group_visit_atomic(group["id"], 30)

    # only the pre-existing solo session exists; visit wrote nothing
    assert _session_count(db) == 1
    assert db.get_credit_balance(leader_id) == 60
