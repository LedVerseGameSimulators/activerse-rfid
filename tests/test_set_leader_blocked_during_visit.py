"""P1: no leader change while group has an open visit."""
import pytest
from fastapi import HTTPException

from api import groups

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def test_set_leader_blocked_during_open_visit(db):
    leader = _make_player(db, "555-p401", "L1", credit_minutes=60)
    other = _make_player(db, "555-p402", "L2")
    company = db.create_company("LeadCo")
    group = db.create_group(company["id"], "LeadTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], other)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "LEADBLK0001")
    db.issue_group_visit_atomic(group["id"], 30, card_id="LEADBLK0001")

    with pytest.raises(HTTPException) as exc:
        groups.set_leader(db, group["id"], other)
    assert exc.value.status_code == 400
    assert "visit" in exc.value.detail.lower()


def test_set_leader_allowed_after_close(db):
    leader = _make_player(db, "555-p403", "L3", credit_minutes=60)
    other = _make_player(db, "555-p404", "L4")
    company = db.create_company("LeadCo2")
    group = db.create_group(company["id"], "LeadTeam2")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], other)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "LEADBLK0002")
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="LEADBLK0002")
    db.close_session(visit["session_id"])
    groups.set_leader(db, group["id"], other)
    assert db.get_group(group["id"])["leader_player_id"] == other
