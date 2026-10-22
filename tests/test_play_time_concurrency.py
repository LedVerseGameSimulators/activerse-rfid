"""P1: concurrent roster add / close under Database._lock."""
import threading

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def test_concurrent_roster_add_and_close(db):
    leader = _make_player(db, "555-p501", "ConcLead", credit_minutes=200)
    joiners = [_make_player(db, f"555-p5{i:02d}", f"J{i}") for i in range(10, 14)]
    company = db.create_company("ConcCo")
    group = db.create_group(company["id"], "ConcTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "CONCCARD001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="CONCCARD001")
    sid = visit["session_id"]
    errors = []

    def add_one(pid):
        try:
            db.add_roster_member_atomic(sid, pid)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=add_one, args=(j,)) for j in joiners]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    roster = db.get_session_roster(sid)
    assert len(roster) == 1 + len(joiners)
    db.close_session(sid)
    again = db.close_session(sid)
    assert again["refunded_minutes"] == 0.0
