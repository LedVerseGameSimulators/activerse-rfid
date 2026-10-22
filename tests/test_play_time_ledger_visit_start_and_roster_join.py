"""P1: append-only play_time_events; roster join credits remaining visit minutes."""
from datetime import datetime, timedelta
from unittest.mock import patch

from api import sessions

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def _ledger_sum(db, player_id, source=None):
    if source:
        rows = db._execute(
            "SELECT minutes FROM play_time_events WHERE player_id = ? AND source = ?",
            (player_id, source),
            fetch="all",
        )
    else:
        rows = db._execute(
            "SELECT minutes FROM play_time_events WHERE player_id = ?",
            (player_id,),
            fetch="all",
        )
    return sum(r["minutes"] for r in rows) if rows else 0.0


def test_visit_start_ledger_on_group_visit(db):
    leader = _make_player(db, "555-p101", "LedgerLead", credit_minutes=60)
    company = db.create_company("LedgerCo")
    group = db.create_group(company["id"], "LedgerTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "LEDGERCARD01")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="LEDGERCARD01")
    assert _ledger_sum(db, leader, "visit_start") == 60.0
    count = db._execute("SELECT COUNT(*) c FROM play_time_events", fetch="one")["c"]
    assert count == 1
    out = sessions.validate_card(db, "LEDGERCARD01")
    assert out["valid"] is True


def test_roster_join_credits_remaining_minutes(db):
    leader = _make_player(db, "555-p102", "JoinLead", credit_minutes=120)
    joiner = _make_player(db, "555-p103", "Joiner")
    company = db.create_company("JoinCo")
    group = db.create_group(company["id"], "JoinTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "JOINLEAD0001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="JOINLEAD0001")
    sid = visit["session_id"]

    future_expiry = (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future_expiry, sid))

    with patch.object(db, "_minutes_remaining_clock", return_value=30.0):
        db.add_roster_member_atomic(sid, joiner)

    assert _ledger_sum(db, joiner, "roster_join") == 30.0
    assert _ledger_sum(db, joiner, "visit_start") == 0.0
    out = sessions.validate_card(db, "JOINLEAD0001")
    assert out["valid"] is True
    assert joiner in out["roster_player_ids"]
