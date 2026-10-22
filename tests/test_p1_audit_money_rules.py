"""Regression tests for P1 audit fixes (refund cap, adjust guards, roster credit)."""
import threading
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from api import groups, sessions

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def _start_visit(db, credit=120, duration=60, card="AUDITCARD001"):
    leader = _make_player(db, f"555-a{duration}", "AuditLead", credit_minutes=credit)
    company = db.create_company("AuditCo")
    group = db.create_group(company["id"], "AuditTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, card)
    visit = db.issue_group_visit_atomic(group["id"], duration, card_id=card)
    return leader, group, visit["session_id"], card


def test_refund_capped_after_free_clock_extension(db):
    leader, _, sid, _ = _start_visit(db, duration=60)
    db.adjust_session(sid, 25, "comp", adjustment_mode="free_clock")
    result = db.close_session(sid)
    # Clock shows ~85 min left but only 60 min were ever paid.
    assert result["refunded_minutes"] <= 60.0
    assert result["refunded_minutes"] == 60.0
    assert db.get_credit_balance(leader) == 120.0  # 60 spent, 60 refunded


def test_refund_after_balance_tied_extension(db):
    leader, _, sid, _ = _start_visit(db, credit=150, duration=60)
    db.adjust_session(sid, 30, "paid extend", adjustment_mode="balance_tied", balance_delta_min=30)
    future = (datetime.now() + timedelta(minutes=90)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    result = db.close_session(sid)
    assert result["refunded_minutes"] <= 90.0
    assert result["refunded_minutes"] == 90.0


def test_refund_after_balance_tied_shrink(db):
    leader, _, sid, _ = _start_visit(db, credit=100, duration=60)
    db.adjust_session(sid, -15, "partial refund", adjustment_mode="balance_tied", balance_delta_min=-15)
    future = (datetime.now() + timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    result = db.close_session(sid)
    assert result["refunded_minutes"] == 45.0
    # 100 - 60 visit + 15 tied shrink credit + 45 close refund
    assert db.get_credit_balance(leader) == 100.0


def test_plain_early_close_unchanged(db):
    leader, _, sid, card = _start_visit(db, credit=100, duration=60, card="PLAINREF001")
    future = (datetime.now() + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    result = db.close_session(sid)
    assert result["refunded_minutes"] == 25.0
    out = sessions.validate_card(db, card)
    assert out["valid"] is False


def test_concurrent_close_single_refund(db):
    leader, _, sid, _ = _start_visit(db, credit=80, duration=40, card="CONCREF001")
    future = (datetime.now() + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    results = []

    def closer():
        results.append(db.close_session(sid))

    threads = [threading.Thread(target=closer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    refunded_total = sum(r["refunded_minutes"] for r in results)
    assert refunded_total == 20.0
    assert db._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE source = 'refund' AND session_id = ?",
        (sid,),
        fetch="one",
    )["c"] == 1


def test_balance_tied_rejects_overdraft(db):
    leader, _, sid, _ = _start_visit(db, credit=70, duration=60)
    with pytest.raises(ValueError, match="Top up"):
        db.adjust_session(
            sid, 30, "too much", adjustment_mode="balance_tied", balance_delta_min=30
        )
    assert db.get_credit_balance(leader) == 10.0


def test_balance_tied_negative_credit_allowed(db):
    leader, _, sid, _ = _start_visit(db, credit=80, duration=60)
    db.adjust_session(sid, -10, "credit back", adjustment_mode="balance_tied", balance_delta_min=-10)
    assert db.get_credit_balance(leader) == 30.0


def test_adjust_past_expiry_rejected_free_and_tied(db):
    _, _, sid, _ = _start_visit(db, duration=60)
    with pytest.raises(ValueError, match="close the session"):
        db.adjust_session(sid, -120, "kill", adjustment_mode="free_clock")
    with pytest.raises(ValueError, match="close the session"):
        db.adjust_session(sid, -120, "kill", adjustment_mode="balance_tied", balance_delta_min=-120)


def test_roster_remove_readd_single_join_credit(db):
    leader, _, sid, _ = _start_visit(db, duration=60)
    joiner = _make_player(db, "555-a999", "ReJoin")
    db.add_roster_member_atomic(sid, joiner)
    db.remove_roster_member(sid, joiner)
    db.add_roster_member_atomic(sid, joiner)
    count = db._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE session_id = ? AND player_id = ? "
        "AND source = 'roster_join'",
        (sid, joiner),
        fetch="one",
    )["c"]
    assert count == 1
    roster = db.get_session_roster(sid)
    assert any(r["player_id"] == joiner for r in roster)


def test_leader_change_blocked_on_expired_unclosed_visit(db):
    leader = _make_player(db, "555-a801", "ExpLead", credit_minutes=80)
    other = _make_player(db, "555-a802", "NewLead")
    company = db.create_company("ExpLeadCo")
    group = db.create_group(company["id"], "ExpLeadTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], other)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "EXPLEAD0001")
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="EXPLEAD0001")
    past = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute(
        "UPDATE player_sessions SET expiry_at = ? WHERE id = ?",
        (past, visit["session_id"]),
    )
    with pytest.raises(HTTPException) as exc:
        groups.set_leader(db, group["id"], other)
    assert exc.value.status_code == 400

    visit2 = db.issue_group_visit_atomic(group["id"], 20, card_id="EXPLEAD0001")
    assert visit2["session_id"] != visit["session_id"]
