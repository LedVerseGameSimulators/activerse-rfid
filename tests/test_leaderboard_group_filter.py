def _make_player(db, phone, name):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    return db.search_custom_by_field("phone_num", phone)[0]["custom_id"]


def test_upsert_central_score_stores_group_id(db):
    player_id = _make_player(db, "555-3001", "Alice")
    db.upsert_central_score({
        "player_id": player_id, "card_id": "C1", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10, "final_score": 10,
        "company_id": None, "group_id": 7,
    })
    row = db._execute(
        "SELECT group_id FROM central_scores WHERE player_id = ?",
        (player_id,), fetch="one",
    )
    assert row["group_id"] == 7


def test_get_leaderboard_filters_by_group_id(db):
    p1 = _make_player(db, "555-3002", "Bob")
    p2 = _make_player(db, "555-3003", "Carl")
    db.upsert_central_score({
        "player_id": p1, "card_id": "C2", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10, "final_score": 10, "group_id": 1,
    })
    db.upsert_central_score({
        "player_id": p2, "card_id": "C3", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 20, "final_score": 20, "group_id": 2,
    })
    rows = db.get_leaderboard(group_id=1)
    assert len(rows) == 1
    assert rows[0]["player_id"] == p1


def test_upsert_central_team_score_stores_group_id(db):
    tsid = db.upsert_central_team_score({
        "session_id": 1, "card_id": "C4", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10, "final_score": 10,
        "member_count": 2, "members_json": "[]", "group_id": 3,
    })
    row = db._execute(
        "SELECT group_id FROM central_team_scores WHERE id = ?", (tsid,), fetch="one"
    )
    assert row["group_id"] == 3


def test_get_team_leaderboard_filters_by_group_id(db):
    db.upsert_central_team_score({
        "session_id": 1, "card_id": "C5", "game": "hoops",
        "played_at": "2026-01-01 00:00:00", "score": 10, "final_score": 10,
        "member_count": 2, "members_json": "[]", "group_id": 1,
    })
    db.upsert_central_team_score({
        "session_id": 2, "card_id": "C6", "game": "hoops",
        "played_at": "2026-01-01 00:00:01", "score": 20, "final_score": 20,
        "member_count": 2, "members_json": "[]", "group_id": 2,
    })
    rows = db.get_team_leaderboard(group_id=1)
    assert len(rows) == 1
    assert rows[0]["card_id"] == "C5"
