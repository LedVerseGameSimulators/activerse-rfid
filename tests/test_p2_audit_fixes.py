"""P2 audit follow-ups (post ccc1b47)."""
import threading

import pytest

from api import groups, players
from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def test_start_visit_rejects_archived_group(db):
    company = db.create_company("ArchVisit Co")
    group = db.create_group(company["id"], "Arch Team")
    leader = _make_player(db, "555-a001", "ArchLead", credit_minutes=60)
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "ARCHVISIT01")
    db.archive_group(group["id"])
    with pytest.raises(ValueError, match="archived"):
        db.issue_group_visit_atomic(group["id"], 30, card_id="ARCHVISIT01")
    db.unarchive_group(group["id"])
    visit = db.issue_group_visit_atomic(group["id"], 30, card_id="ARCHVISIT01")
    assert visit["session_id"] is not None


def test_start_visit_api_rejects_archived_group(db):
    company = db.create_company("ArchAPI Co")
    group = db.create_group(company["id"], "Arch API")
    leader = _make_player(db, "555-a002", "ApiLead", credit_minutes=60)
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    db.archive_group(group["id"])
    with pytest.raises(Exception) as exc:
        groups.start_visit(db, group["id"], 30)
    assert "archived" in str(exc.value).lower()
    db.unarchive_group(group["id"])
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "ARCHAPI002")
    out = groups.start_visit(db, group["id"], 30)
    assert out["session_id"]


def test_add_member_rejects_archived_group(db):
    company = db.create_company("ArchMem Co")
    group = db.create_group(company["id"], "Arch Mem")
    player_id = _make_player(db, "555-a003", "Mem")
    db.archive_group(group["id"])
    with pytest.raises(ValueError, match="archived"):
        db.add_group_member_atomic(group["id"], player_id)


def test_delete_player_removes_solo_group_without_history(db):
    p = players.register_player(db, "Del Solo", "555-a010")
    pid = p["id"]
    solo_id = db.get_solo_group_id(pid)
    assert solo_id is not None
    db.delete_player(pid)
    assert db.get_group(solo_id) is None
    assert db.get_company_membership(pid) is None
    assert not db.search_custom_tb_by_id(pid)


def test_delete_player_archives_solo_group_with_score_history(db):
    p = players.register_player(db, "Scored Solo", "555-a011")
    pid = p["id"]
    solo_id = db.get_solo_group_id(pid)
    db.upsert_central_score({
        "player_id": pid, "card_id": "SCORESOLO1", "game": "hoops",
        "played_at": "2026-06-01 12:00:00", "score": 7, "group_id": solo_id,
    })
    db.delete_player(pid)
    g = db.get_group(solo_id)
    assert g is not None
    assert g["archived_at"] is not None
    assert g["kind"] == "solo"


def test_delete_player_refuses_team_leader(db):
    company = db.create_company("DelLead Co")
    group = db.create_group(company["id"], "Lead Team")
    leader = _make_player(db, "555-a012", "TeamLead")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    with pytest.raises(ValueError, match="leader"):
        db.delete_player(leader)


def test_solo_group_duplicate_name_uses_player_id_suffix(db):
    p1 = players.register_player(db, "Same Name", "555-a020")
    p2 = players.register_player(db, "Same Name", "555-a021")
    g1 = db.get_group(db.get_solo_group_id(p1["id"]))
    g2 = db.get_group(db.get_solo_group_id(p2["id"]))
    assert g1["name"] == "Same Name"
    assert g2["name"] == f"Same Name ({p2['id']})"


def test_issue_session_blocks_team_member_allows_solo_only(db):
    company = db.create_company("Iss Co")
    team = db.create_group(company["id"], "Iss Team")
    pid = _make_player(db, "555-a030", "IssPlayer", credit_minutes=120)
    db.ensure_solo_group_for_player(pid)
    db.add_group_member_atomic(team["id"], pid)
    with pytest.raises(ValueError, match="team"):
        db.issue_session_atomic(pid, "ISSCARD0001", 30)
    db.remove_group_member(team["id"], pid)
    sid, *_ = db.issue_session_atomic(pid, "ISSCARD0002", 30)
    assert sid is not None


def test_concurrent_start_visit_two_groups_one_wins(db):
    company = db.create_company("Race Co")
    g1 = db.create_group(company["id"], "Race1")
    g2 = db.create_group(company["id"], "Race2")
    leader = _make_player(db, "555-a040", "RaceLead", credit_minutes=200)
    db.add_group_member_atomic(g1["id"], leader)
    db.add_group_member_atomic(g2["id"], leader)
    db.set_group_leader(g1["id"], leader)
    db.set_group_leader(g2["id"], leader)
    _bind_card(db, leader, "RACECARD001")
    results = []
    errors = []

    def start(gid):
        try:
            results.append(db.issue_group_visit_atomic(gid, 30, card_id="RACECARD001"))
        except ValueError as e:
            errors.append(str(e))

    t1 = threading.Thread(target=start, args=(g1["id"],))
    t2 = threading.Thread(target=start, args=(g2["id"],))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert len(results) == 1
    assert len(errors) == 1
