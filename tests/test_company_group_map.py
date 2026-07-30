def _make_player(db, phone, name):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    return db.search_custom_by_field("phone_num", phone)[0]["custom_id"]


def test_get_company_group_map_returns_company_and_group(db):
    company = db.create_company("Acme")
    group = db.create_group(company["id"], "Team A")
    player_id = _make_player(db, "555-4001", "Alice")
    db.add_group_member_atomic(group["id"], player_id)

    result = db.get_company_group_map([player_id])

    assert result[player_id]["company_id"] == company["id"]
    assert result[player_id]["group_id"] == group["id"]


def test_get_company_group_map_company_only_no_group(db):
    company = db.create_company("Acme")
    player_id = _make_player(db, "555-4002", "Bob")
    db.add_company_member_atomic(company["id"], player_id)

    result = db.get_company_group_map([player_id])

    assert result[player_id]["company_id"] == company["id"]
    assert result[player_id]["group_id"] is None


def test_get_company_group_map_unaffiliated_player_absent(db):
    player_id = _make_player(db, "555-4003", "Carl")
    result = db.get_company_group_map([player_id])
    assert player_id not in result


def test_get_company_group_map_empty_input(db):
    assert db.get_company_group_map([]) == {}
