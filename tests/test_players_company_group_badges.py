from api import players, companies, groups


def _make_player(db, phone, name):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    return db.search_custom_by_field("phone_num", phone)[0]["custom_id"]


def test_list_players_includes_group_badge(db):
    company = companies.create_company(db, "Acme")
    group = groups.create_group(db, company["id"], "Team A")
    player_id = _make_player(db, "555-6001", "Alice")
    groups.add_member(db, group["id"], player_id=player_id)

    rows = players.list_players(db)
    row = next(r for r in rows if r["id"] == player_id)
    assert row["company_id"] == company["id"]
    assert row["group_id"] == group["id"]
    assert row["group_name"] == "Team A"


def test_list_players_unaffiliated_has_no_badges(db):
    player_id = _make_player(db, "555-6002", "Bob")
    rows = players.list_players(db)
    row = next(r for r in rows if r["id"] == player_id)
    assert row["company_id"] is None
    assert row["group_id"] is None


def test_get_player_includes_company_badge_without_group(db):
    company = companies.create_company(db, "Acme")
    player_id = _make_player(db, "555-6003", "Carl")
    db.add_company_member_atomic(company["id"], player_id)

    row = players.get_player(db, player_id)
    assert row["company_id"] == company["id"]
    assert row["company_name"] == "Acme"
    assert row["group_id"] is None
