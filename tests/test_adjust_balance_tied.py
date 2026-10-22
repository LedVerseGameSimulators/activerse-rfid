"""P1: balance-tied session adjustments."""
from datetime import datetime, timedelta

from api import sessions

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def test_balance_tied_negative_adjusts_wallet_and_clock(db):
    leader = _make_player(db, "555-p301", "AdjLead", credit_minutes=100)
    company = db.create_company("AdjCo")
    group = db.create_group(company["id"], "AdjTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "ADJLEAD0001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="ADJLEAD0001")
    sid = visit["session_id"]
    # balance 40 after 60 min visit
    before_expiry = db.get_session(sid)["expiry_at"]

    db.adjust_session(sid, -15, "correction", adjustment_mode="balance_tied", balance_delta_min=-15)
    after = db.get_session(sid)
    exp_before = datetime.strptime(before_expiry, "%Y-%m-%d %H:%M:%S")
    exp_after = datetime.strptime(after["expiry_at"], "%Y-%m-%d %H:%M:%S")
    assert (exp_after - exp_before).total_seconds() == -15 * 60
    assert db.get_credit_balance(leader) == 55.0  # 40 + 15 returned

    adj = db._execute(
        "SELECT adjustment_mode, balance_delta_min FROM session_adjustments WHERE session_id = ?",
        (sid,),
        fetch="one",
    )
    assert adj["adjustment_mode"] == "balance_tied"
    assert adj["balance_delta_min"] == -15.0
    out = sessions.validate_card(db, "ADJLEAD0001")
    assert out["valid"] is True


def test_free_clock_does_not_touch_balance(db):
    leader = _make_player(db, "555-p302", "FreeClk", credit_minutes=80)
    company = db.create_company("FreeCo")
    group = db.create_group(company["id"], "FreeTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "FREECLK0001")
    visit = db.issue_group_visit_atomic(group["id"], 40, card_id="FREECLK0001")
    sid = visit["session_id"]
    bal = db.get_credit_balance(leader)
    db.adjust_session(sid, 10, "comp", adjustment_mode="free_clock")
    assert db.get_credit_balance(leader) == bal
    assert db._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE source = 'adjust'",
        fetch="one",
    )["c"] == 0
