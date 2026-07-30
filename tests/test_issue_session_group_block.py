import pytest


def _make_player(db, phone, name, credit_minutes=120):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    player_id = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    if credit_minutes:
        db.add_credit(player_id, credit_minutes, 0)
    return player_id


def test_issue_session_atomic_blocks_solo_play_while_grouped(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-1001", "Alice")
    db.add_group_member_atomic(group["id"], player_id)

    with pytest.raises(ValueError, match="team"):
        db.issue_session_atomic(player_id, "CARD001", 30)


def test_issue_session_atomic_allows_solo_for_unaffiliated_player(db):
    player_id = _make_player(db, "555-1002", "Bob")
    sid, issued_at, expiry, balance_after = db.issue_session_atomic(player_id, "CARD002", 30)
    assert sid is not None
    assert balance_after == 90


def test_issue_session_atomic_stamps_company_for_ungrouped_company_member(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-1003", "Carl")
    db.add_company_member_atomic(company["id"], player_id)

    sid, *_ = db.issue_session_atomic(player_id, "CARD003", 30)

    session = db._execute(
        "SELECT company_id, group_id FROM player_sessions WHERE id = ?",
        (sid,), fetch="one",
    )
    assert session["company_id"] == company["id"]
    assert session["group_id"] is None


def test_issue_session_atomic_no_company_stamp_for_unaffiliated_player(db):
    player_id = _make_player(db, "555-1004", "Dana")
    sid, *_ = db.issue_session_atomic(player_id, "CARD004", 30)
    session = db._execute(
        "SELECT company_id FROM player_sessions WHERE id = ?", (sid,), fetch="one"
    )
    assert session["company_id"] is None
