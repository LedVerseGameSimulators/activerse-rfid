"""Step 0 contract: poller ingest, validate fields, leaderboard raw score + filters."""
import importlib
import sys

import pytest

from api import poller, sessions


def _make_player(db, phone, name, credit_minutes=0):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    player_id = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    if credit_minutes:
        db.add_credit(player_id, credit_minutes, 0)
    return player_id


def _bind_card(db, player_id, card_id):
    db._execute(
        "UPDATE custom_info SET card_id = ? WHERE custom_id = ?",
        (card_id, player_id),
    )


def _insert_session(db, player_id, card_id, issued_at, expiry_at, *,
                    closed_at=None, group_id=None, company_id=None):
    con = db._conn()
    cur = con.execute(
        "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
        "duration_min, closed_at, group_id, company_id) VALUES (?, ?, ?, ?, 60, ?, ?, ?)",
        (player_id, card_id, issued_at, expiry_at, closed_at, group_id, company_id),
    )
    sid = cur.lastrowid
    con.execute(
        "INSERT INTO session_roster (session_id, player_id) VALUES (?, ?)",
        (sid, player_id),
    )
    con.commit()
    con.close()
    return sid


def test_leaderboard_orders_by_raw_score_not_final(db):
    p1 = _make_player(db, "555-4001", "HighRaw")
    p2 = _make_player(db, "555-4002", "HighFinal")
    db.upsert_central_score({
        "player_id": p1, "card_id": "LB1", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 100, "final_score": 10,
    })
    db.upsert_central_score({
        "player_id": p2, "card_id": "LB2", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 50, "final_score": 500,
    })
    rows = db.get_leaderboard(limit=10)
    assert rows[0]["player_id"] == p1
    assert rows[1]["player_id"] == p2


def test_get_session_for_card_at_no_fallback_to_newer_session(db):
    leader = _make_player(db, "555-4003", "LatePoll")
    _bind_card(db, leader, "CARDLATE01")
    _insert_session(
        db, leader, "CARDLATE01",
        "2026-06-01 14:00:00", "2099-01-01 00:00:00",
        group_id=99,
    )
    session = db.get_session_for_card_at("CARDLATE01", "2026-06-01 10:00:00")
    assert session is None


def test_late_play_not_attributed_to_newer_active_session(db):
    leader = _make_player(db, "555-4004", "Hist")
    _bind_card(db, leader, "CARDHIST01")
    _insert_session(
        db, leader, "CARDHIST01",
        "2026-06-01 14:00:00", "2099-01-01 00:00:00",
        group_id=77,
    )
    poller._ingest_game_row(db, "hoops", {
        "card_id": "CARDHIST01",
        "score": 120,
        "final_score": 120,
        "ts": "2026-06-01 10:00:00",
        "level": "1",
    })
    row = db._execute(
        "SELECT group_id, session_id FROM central_team_scores WHERE card_id = ?",
        ("CARDHIST01",), fetch="one",
    )
    assert row["group_id"] is None
    assert row["session_id"] is None
    attributed = db._execute(
        "SELECT COUNT(*) c FROM central_scores WHERE player_id IS NOT NULL",
        fetch="one",
    )["c"]
    assert attributed == 0


def test_get_session_for_card_at_falsy_played_at_returns_none(db):
    leader = _make_player(db, "555-4014", "NoTsLookup")
    _bind_card(db, leader, "NOTSLOOKUP01")
    _insert_session(
        db, leader, "NOTSLOOKUP01",
        "2026-06-01 10:00:00", "2099-01-01 00:00:00",
        group_id=11,
    )
    assert db.get_session_for_card_at("NOTSLOOKUP01", "") is None
    assert db.get_session_for_card_at("NOTSLOOKUP01", None) is None


def test_ingest_without_ts_not_bound_to_new_active_session(db):
    leader = _make_player(db, "555-4015", "NoTsIngest", credit_minutes=120)
    company = db.create_company("NoTsCo")
    group = db.create_group(company["id"], "NoTsTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "NOTSINGEST01")
    old = db.issue_group_visit_atomic(group["id"], 30, card_id="NOTSINGEST01")
    db.close_session(old["session_id"])
    new = db.issue_group_visit_atomic(group["id"], 30, card_id="NOTSINGEST01")

    poller._ingest_game_row(db, "hoops", {
        "card_id": "NOTSINGEST01",
        "score": 55,
        "level": "1",
    })

    row = db._execute(
        "SELECT session_id, group_id FROM central_team_scores WHERE card_id = ?",
        ("NOTSINGEST01",), fetch="one",
    )
    assert row["session_id"] is None
    assert row["group_id"] is None
    assert row["session_id"] != new["session_id"]
    assert db._execute(
        "SELECT COUNT(*) c FROM central_scores WHERE player_id IS NOT NULL",
        fetch="one",
    )["c"] == 0


def test_garbage_roster_player_ids_json_does_not_abort_ingest(db):
    leader = _make_player(db, "555-4016", "BadJson", credit_minutes=60)
    company = db.create_company("JsonCo")
    group = db.create_group(company["id"], "JsonTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "BADJSONCARD1")
    sid = db.issue_group_visit_atomic(group["id"], 30, card_id="BADJSONCARD1")["session_id"]

    poller._ingest_game_row(db, "hoops", {
        "card_id": "BADJSONCARD1",
        "score": 77,
        "ts": "2026-06-05 12:00:00",
        "level": "1",
        "session_id": sid,
        "group_id": group["id"],
        "roster_player_ids": "{not-json",
    })

    row = db._execute(
        "SELECT session_id, score FROM central_team_scores WHERE card_id = ?",
        ("BADJSONCARD1",), fetch="one",
    )
    assert row["session_id"] == sid
    assert row["score"] == 77


def test_team_battle_two_cards_two_linked_team_rows(db):
    company = db.create_company("TB Co")
    g1 = db.create_group(company["id"], "Red")
    g2 = db.create_group(company["id"], "Blue")
    l1 = _make_player(db, "555-4005", "RedLead", credit_minutes=60)
    l2 = _make_player(db, "555-4006", "BlueLead", credit_minutes=60)
    db.add_group_member_atomic(g1["id"], l1)
    db.add_group_member_atomic(g2["id"], l2)
    db.set_group_leader(g1["id"], l1)
    db.set_group_leader(g2["id"], l2)
    _bind_card(db, l1, "REDCARD0001")
    _bind_card(db, l2, "BLUECARD001")
    m2 = _make_player(db, "555-4007", "RedMate")
    db.add_group_member_atomic(g1["id"], m2)

    s1 = db.issue_group_visit_atomic(g1["id"], 30, card_id="REDCARD0001")["session_id"]
    s2 = db.issue_group_visit_atomic(g2["id"], 30, card_id="BLUECARD001")["session_id"]

    poller._ingest_game_row(db, "hoops", {
        "card_id": "REDCARD0001",
        "card_id2": "BLUECARD001",
        "score": 200,
        "score2": 180,
        "play_mode": "team_battle",
        "ts": "2026-06-02 12:00:00",
        "level": "1",
        "session_id": s1,
        "group_id": g1["id"],
        "roster_size_at_play": 2,
        "roster_player_ids": [l1, m2],
        "session_id2": s2,
        "group_id2": g2["id"],
        "roster_size_at_play2": 1,
        "roster_player_ids2": [l2],
    })

    teams = db._execute(
        "SELECT card_id, group_id, score, member_count, match_key, two_card_play, "
        "opponent_group_id, opponent_card_id FROM central_team_scores ORDER BY player_slot",
        fetch="all",
    )
    assert len(teams) == 2
    assert teams[0]["group_id"] == g1["id"]
    assert teams[0]["member_count"] == 2
    assert teams[0]["score"] == 200
    assert teams[1]["group_id"] == g2["id"]
    assert teams[1]["member_count"] == 1
    assert teams[1]["score"] == 180
    assert teams[0]["match_key"] == teams[1]["match_key"]
    assert teams[0]["two_card_play"] == 1
    assert teams[0]["opponent_group_id"] == g2["id"]
    assert teams[1]["opponent_group_id"] == g1["id"]

    solo_red = db._execute(
        "SELECT score FROM central_scores WHERE player_id = ? ORDER BY player_id",
        (l1,), fetch="one",
    )
    solo_mate = db._execute(
        "SELECT score FROM central_scores WHERE player_id = ?", (m2,), fetch="one",
    )
    solo_blue = db._execute(
        "SELECT score FROM central_scores WHERE player_id = ?", (l2,), fetch="one",
    )
    assert solo_red["score"] == 100.0
    assert solo_mate["score"] == 100.0
    assert solo_blue["score"] == 180.0


def test_same_session_guard_ingests_slot_one_only(db):
    leader = _make_player(db, "555-4008", "DupSess", credit_minutes=60)
    company = db.create_company("Dup")
    group = db.create_group(company["id"], "DupTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "DUPCARD0001")
    sid = db.issue_group_visit_atomic(group["id"], 30, card_id="DUPCARD0001")["session_id"]

    poller._ingest_game_row(db, "hoops", {
        "card_id": "DUPCARD0001",
        "card_id2": "DUPCARD0002",
        "score": 90,
        "score2": 80,
        "play_mode": "team_battle",
        "ts": "2026-06-03 12:00:00",
        "level": "1",
        "session_id": sid,
        "session_id2": sid,
        "group_id": group["id"],
        "group_id2": group["id"],
    })

    count = db._execute(
        "SELECT COUNT(*) c FROM central_team_scores", fetch="one",
    )["c"]
    assert count == 1
    row = db._execute(
        "SELECT two_card_play, match_key FROM central_team_scores", fetch="one",
    )
    assert row["two_card_play"] == 0
    assert row["match_key"] is None


def test_stamped_roster_size_beats_live_roster_after_change(db):
    leader = _make_player(db, "555-4009", "StampN", credit_minutes=60)
    m2 = _make_player(db, "555-4010", "Extra")
    company = db.create_company("Stamp")
    group = db.create_group(company["id"], "StampTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], m2)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "STAMPCARD01")
    sid = db.issue_group_visit_atomic(group["id"], 30, card_id="STAMPCARD0001")["session_id"]
    m3 = _make_player(db, "555-4011", "LateJoin")
    db.add_roster_member(sid, m3)

    poller._ingest_game_row(db, "hoops", {
        "card_id": "STAMPCARD0001",
        "score": 300,
        "ts": "2026-06-04 12:00:00",
        "level": "1",
        "session_id": sid,
        "group_id": group["id"],
        "roster_size_at_play": 2,
        "roster_player_ids": [leader, m2],
    })

    shares = db._execute(
        "SELECT player_id, score FROM central_scores WHERE session_id = ? ORDER BY player_id",
        (sid,), fetch="all",
    )
    assert len(shares) == 2
    assert all(r["score"] == 150.0 for r in shares)


def test_leaderboard_play_mode_size_and_two_card_filters(db):
    p1 = _make_player(db, "555-4017", "FilterA")
    p2 = _make_player(db, "555-4018", "FilterB")
    db.upsert_central_score({
        "player_id": p1, "card_id": "F1", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10,
        "play_mode": "quick_play", "roster_size_at_play": 1, "two_card_play": 0,
    })
    db.upsert_central_score({
        "player_id": p2, "card_id": "F2", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 20,
        "play_mode": "team_battle", "roster_size_at_play": 3, "two_card_play": 1,
    })
    db.upsert_central_score({
        "player_id": None, "card_id": "FGHOST", "game": "hoops",
        "played_at": "2026-01-01 00:00:02", "score": 999,
        "play_mode": "quick_play",
    })
    assert len(db.get_leaderboard(limit=50)) == 2
    qp = db.get_leaderboard(play_mode="quick_play")
    assert len(qp) == 1 and qp[0]["card_id"] == "F1"
    tb = db.get_leaderboard(play_mode="team_battle", min_size=2, max_size=4)
    assert len(tb) == 1 and tb[0]["card_id"] == "F2"
    two = db.get_leaderboard(two_card=True)
    assert len(two) == 1 and two[0]["card_id"] == "F2"
    not_two = db.get_leaderboard(two_card=False)
    assert len(not_two) == 1 and not_two[0]["card_id"] == "F1"


def test_team_leaderboard_includes_single_member_groups(db):
    db.upsert_central_team_score({
        "session_id": 1, "card_id": "SOLOTEAM", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 42,
        "member_count": 1, "members_json": "[]", "group_id": 5,
    })
    rows = db.get_team_leaderboard()
    assert len(rows) == 1
    assert rows[0]["member_count"] == 1


def test_team_leaderboard_excludes_unattributed_team_rows(db):
    db.upsert_central_team_score({
        "session_id": None, "card_id": "GHOSTTEAM", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 99,
        "member_count": 1, "members_json": "[]", "group_id": None,
    })
    db.upsert_central_team_score({
        "session_id": 2, "card_id": "REALTEAM", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 10,
        "member_count": 1, "members_json": "[]", "group_id": 3,
    })
    rows = db.get_team_leaderboard()
    assert len(rows) == 1
    assert rows[0]["card_id"] == "REALTEAM"


def test_validate_card_returns_group_and_roster_fields(db):
    leader = _make_player(db, "555-4012", "Valid", credit_minutes=60)
    mate = _make_player(db, "555-4013", "Mate")
    company = db.create_company("ValidCo")
    group = db.create_group(company["id"], "ValidTeam")
    db.add_group_member_atomic(group["id"], leader)
    db.add_group_member_atomic(group["id"], mate)
    db.set_group_leader(group["id"], leader)
    _bind_card(db, leader, "VALIDCARD001")
    db.issue_group_visit_atomic(group["id"], 30, card_id="VALIDCARD001")

    out = sessions.validate_card(db, "VALIDCARD001")
    assert out["valid"] is True
    assert out["group_id"] == group["id"]
    assert out["roster_size"] == 2
    assert set(out["roster_player_ids"]) == {leader, mate}
