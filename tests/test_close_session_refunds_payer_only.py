"""P1: early close refunds unused clock minutes to payer only."""
from datetime import datetime, timedelta

from api import sessions

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def test_close_refunds_payer_not_member(db):
    leader = _make_player(db, "555-p201", "Payer", credit_minutes=100)
    member = _make_player(db, "555-p202", "Member", credit_minutes=50)
    company = db.create_company("RefundCo")
    group = db.create_group(company["id"], "RefundTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], member)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "REFUNDPAY001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="REFUNDPAY001")
    sid = visit["session_id"]
    # Leader paid 60 → balance 40; member still 50
    assert db.get_credit_balance(leader) == 40.0

    future = (datetime.now() + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))

    result = db.close_session(sid)
    assert result["refunded_minutes"] == 25.0
    assert db.get_credit_balance(leader) == 65.0
    assert db.get_credit_balance(member) == 50.0

    refund_rows = db._execute(
        "SELECT minutes FROM play_time_events WHERE source = 'refund' AND player_id = ?",
        (leader,),
        fetch="all",
    )
    assert len(refund_rows) == 1
    assert refund_rows[0]["minutes"] == 25.0


def test_double_close_idempotent_no_double_refund(db):
    leader = _make_player(db, "555-p203", "Twice", credit_minutes=80)
    company = db.create_company("TwiceCo")
    group = db.create_group(company["id"], "TwiceTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "TWICECARD01")
    visit = db.issue_group_visit_atomic(group["id"], 40, card_id="TWICECARD01")
    sid = visit["session_id"]
    future = (datetime.now() + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))

    first = db.close_session(sid)
    balance_after_first = db.get_credit_balance(leader)
    second = db.close_session(sid)
    assert first["refunded_minutes"] == 20.0
    assert second["refunded_minutes"] == 0.0
    assert db.get_credit_balance(leader) == balance_after_first
    refunds = db._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE source = 'refund'",
        fetch="one",
    )["c"]
    assert refunds == 1


def test_expired_visit_close_refund_zero(db):
    leader = _make_player(db, "555-p204", "ExpiredClose", credit_minutes=60)
    company = db.create_company("ExpCo")
    group = db.create_group(company["id"], "ExpTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "EXPCLOSE001")
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="EXPCLOSE001")
    sid = visit["session_id"]
    past = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (past, sid))
    balance_before = db.get_credit_balance(leader)

    result = db.close_session(sid)
    assert result["refunded_minutes"] == 0.0
    assert db.get_credit_balance(leader) == balance_before


def test_validate_after_close_still_ok_for_new_visit(db):
    leader = _make_player(db, "555-p205", "ReVal", credit_minutes=120)
    company = db.create_company("ReValCo")
    group = db.create_group(company["id"], "ReValTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "REVALCARD01")
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="REVALCARD01")
    db.close_session(visit["session_id"])
    visit2 = db.issue_group_visit_atomic(group["id"], 30, card_id="REVALCARD01")
    out = sessions.validate_card(db, "REVALCARD01")
    assert out["valid"] is True
    assert out["session_id"] == visit2["session_id"]
