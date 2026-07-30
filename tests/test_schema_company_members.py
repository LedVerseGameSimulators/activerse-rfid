import sqlite3


def _make_player(db, phone, name):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    return db.search_custom_by_field("phone_num", phone)[0]["custom_id"]


def test_company_members_table_exists(db):
    con = db._conn()
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    con.close()
    assert "company_members" in tables


def test_company_members_enforces_one_company_per_player(db):
    company_a = db.create_company("Acme")
    company_b = db.create_company("Beta")
    player_id = _make_player(db, "555-0001", "Alice")

    con = db._conn()
    con.execute(
        "INSERT INTO company_members (company_id, player_id, joined_at) VALUES (?, ?, ?)",
        (company_a["id"], player_id, "2026-01-01"),
    )
    con.commit()
    try:
        con.execute(
            "INSERT INTO company_members (company_id, player_id, joined_at) VALUES (?, ?, ?)",
            (company_b["id"], player_id, "2026-01-01"),
        )
        con.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    finally:
        con.close()
    assert raised, "player_id should be UNIQUE on company_members"


def test_groups_company_id_is_nullable(db):
    group = db.create_group(None, "Birthday Party Team")
    assert group["company_id"] is None


def test_walk_in_group_appears_in_list_groups(db):
    db.create_group(None, "Birthday Party Team")
    rows = db.list_groups()
    assert any(g["name"] == "Birthday Party Team" for g in rows)


def test_list_groups_walk_in_only_filter(db):
    company = db.create_company("Acme")
    db.create_group(company["id"], "Acme Team")
    db.create_group(None, "Birthday Party Team")
    rows = db.list_groups(walk_in_only=True)
    names = {g["name"] for g in rows}
    assert names == {"Birthday Party Team"}


def test_group_members_unique_on_player_id(db):
    company = db.create_company("Acme")
    group_a = db.create_group(company["id"], "Team A")
    group_b = db.create_group(company["id"], "Team B")
    player_id = _make_player(db, "555-0099", "Bob")

    con = db._conn()
    con.execute(
        "INSERT INTO group_members (group_id, player_id) VALUES (?, ?)",
        (group_a["id"], player_id),
    )
    con.commit()
    try:
        con.execute(
            "INSERT INTO group_members (group_id, player_id) VALUES (?, ?)",
            (group_b["id"], player_id),
        )
        con.commit()
        raised = False
    except sqlite3.IntegrityError:
        raised = True
    finally:
        con.close()
    assert raised, "player_id should be UNIQUE on group_members (one group at a time)"
