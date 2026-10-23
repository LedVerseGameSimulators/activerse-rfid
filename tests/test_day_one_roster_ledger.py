"""Day-one roster members receive full-visit roster_join ledger credits."""
import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

from api import stats
from api import sessions

from tests.test_step0_poller_and_leaderboard import _bind_card, _make_player


def _ledger_rows(db, session_id, player_id, source):
    return db._execute(
        "SELECT minutes, earned_at, source FROM play_time_events "
        "WHERE session_id = ? AND player_id = ? AND source = ?",
        (session_id, player_id, source),
        fetch="all",
    )


def test_three_person_group_day_one_ledger_and_wallet(db):
    leader = _make_player(db, "555-d001", "DLead", credit_minutes=200)
    m1 = _make_player(db, "555-d002", "DM1")
    m2 = _make_player(db, "555-d003", "DM2")
    bal_m1 = db.get_credit_balance(m1)
    bal_m2 = db.get_credit_balance(m2)
    company = db.create_company("DayOneCo")
    group = db.create_group(company["id"], "DayOneTeam")
    for pid in (leader, m1, m2):
        db.add_group_member_atomic(group["id"], pid)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "DAYONE00001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="DAYONE00001")
    sid = visit["session_id"]
    issued = visit["issued_at"]

    assert len(_ledger_rows(db, sid, leader, "visit_start")) == 1
    assert _ledger_rows(db, sid, leader, "visit_start")[0]["minutes"] == 60.0
    assert len(_ledger_rows(db, sid, leader, "roster_join")) == 0

    for mid in (m1, m2):
        rows = _ledger_rows(db, sid, mid, "roster_join")
        assert len(rows) == 1
        assert rows[0]["minutes"] == 60.0
        assert rows[0]["earned_at"] == issued

    assert db.get_credit_balance(m1) == bal_m1
    assert db.get_credit_balance(m2) == bal_m2


def test_close_refund_unchanged_with_day_one_credits(db):
    leader = _make_player(db, "555-d010", "RefLead", credit_minutes=100)
    m1 = _make_player(db, "555-d011", "RefM")
    company = db.create_company("RefCo2")
    group = db.create_group(company["id"], "RefG2")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], m1)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "DAYREF00002")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="DAYREF00002")
    sid = visit["session_id"]
    future = (datetime.now() + timedelta(minutes=25)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    bal_before = db.get_credit_balance(leader)
    result = db.close_session(sid)
    assert result["refunded_minutes"] == 25.0
    assert db.get_credit_balance(leader) == bal_before + 25.0


def test_day_one_remove_readd_no_extra_credit(db):
    leader = _make_player(db, "555-d020", "ReDLead", credit_minutes=120)
    member = _make_player(db, "555-d021", "ReDM")
    company = db.create_company("ReDCo")
    group = db.create_group(company["id"], "ReDTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], member)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "DAYREADD001")
    visit = db.issue_group_visit_atomic(group["id"], 45, card_id="DAYREADD001")
    sid = visit["session_id"]
    db.remove_roster_member(sid, member)
    db.add_roster_member_atomic(sid, member)
    count = db._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE session_id = ? AND player_id = ? "
        "AND source = 'roster_join'",
        (sid, member),
        fetch="one",
    )["c"]
    assert count == 1


def test_late_join_still_remaining_minutes(db):
    leader = _make_player(db, "555-d030", "LateL", credit_minutes=120)
    joiner = _make_player(db, "555-d031", "LateJ")
    company = db.create_company("LateCo")
    group = db.create_group(company["id"], "LateTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "LATEJOIN001")
    visit = db.issue_group_visit_atomic(group["id"], 60, card_id="LATEJOIN001")
    sid = visit["session_id"]
    future = (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    db._execute("UPDATE player_sessions SET expiry_at = ? WHERE id = ?", (future, sid))
    with patch.object(db, "_minutes_remaining_clock", return_value=30.0):
        db.add_roster_member_atomic(sid, joiner)
    row = db._execute(
        "SELECT minutes FROM play_time_events WHERE session_id = ? AND player_id = ? "
        "AND source = 'roster_join'",
        (sid, joiner),
        fetch="one",
    )
    assert row["minutes"] == 30.0


def test_session_stats_include_day_one_members(db):
    leader = _make_player(db, "555-d040", "StatL", credit_minutes=90)
    member = _make_player(db, "555-d041", "StatM")
    company = db.create_company("StatCo")
    group = db.create_group(company["id"], "StatTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], member)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "STATDAY0001")
    visit = db.issue_group_visit_atomic(group["id"], 50, card_id="STATDAY0001")
    sid = visit["session_id"]
    out = stats.get_session_stats(db, sid)
    member_row = next(r for r in out["roster"] if r["player_id"] == member)
    assert member_row["joined_via"] == "roster_join"
    assert member_row["joined_at"] == visit["issued_at"]
    assert member_row["earned_min"] == 50.0
    payer_row = next(r for r in out["roster"] if r["player_id"] == leader)
    assert payer_row["joined_via"] == "visit_start"


def test_backfill_idempotent_on_populated_db(db, tmp_path, monkeypatch):
    import sqlite3

    leader = _make_player(db, "555-d050", "BfLead", credit_minutes=80)
    m1 = _make_player(db, "555-d051", "BfM1")
    m2 = _make_player(db, "555-d052", "BfM2")
    company = db.create_company("BfCo")
    group = db.create_group(company["id"], "BfTeam")
    for pid in (leader, m1, m2):
        db.add_group_member_atomic(group["id"], pid)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "BACKFILL001")
    visit = db.issue_group_visit_atomic(group["id"], 40, card_id="BACKFILL001")
    sid = visit["session_id"]
    db._execute(
        "DELETE FROM play_time_events WHERE session_id = ? AND source = 'roster_join'",
        (sid,),
    )
    assert db._execute("SELECT COUNT(*) c FROM play_time_events", fetch="one")["c"] == 1

    db_path = tmp_path / "backfill.sqlite"
    src = db._conn()
    dst = sqlite3.connect(str(db_path))
    src.backup(dst)
    dst.close()
    src.close()

    con = sqlite3.connect(str(db_path))
    pte_before = con.execute("SELECT COUNT(*) FROM play_time_events").fetchone()[0]
    sess_before = con.execute("SELECT COUNT(*) FROM player_sessions").fetchone()[0]
    roster_before = con.execute("SELECT COUNT(*) FROM session_roster").fetchone()[0]
    con.close()

    monkeypatch.setenv("DB_PATH", str(db_path))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")
    db2 = database_mod.Database()
    added = db2._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE notes = 'backfill:day_one_roster'",
        fetch="one",
    )["c"]
    assert added == 2
    assert db2._execute("SELECT COUNT(*) c FROM player_sessions", fetch="one")["c"] == sess_before
    assert db2._execute("SELECT COUNT(*) c FROM session_roster", fetch="one")["c"] == roster_before

    pte_after_first = db2._execute("SELECT COUNT(*) c FROM play_time_events", fetch="one")["c"]
    assert pte_after_first == pte_before + 2
    db3 = database_mod.Database()
    assert db3._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE notes = 'backfill:day_one_roster'",
        fetch="one",
    )["c"] == 2
    added_second = db3._execute(
        "SELECT COUNT(*) c FROM play_time_events WHERE notes = 'backfill:day_one_roster'",
        fetch="one",
    )["c"]
    assert added == added_second
