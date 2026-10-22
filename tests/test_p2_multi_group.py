"""Phase 2: multi-group, solo groups, walk-in, archive, migrations."""
import importlib
import sqlite3
import sys

import pytest

from api import players


def _make_player(db, phone, name, credit=0):
    db.insert_to_table_custom_tb(phone, name, "1", "0", "", "")
    pid = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    if credit:
        db.add_credit(pid, credit, 0)
    return pid


def test_register_creates_walk_in_and_solo_group(db):
    p = players.register_player(db, "Solo Reg", "555-p201", email="a@test.com")
    walk_id = db.get_walk_in_company_id()
    mem = db.get_company_membership(p["id"])
    assert mem["company_id"] == walk_id
    solo_id = db.get_solo_group_id(p["id"])
    assert solo_id is not None
    g = db.get_group(solo_id)
    assert g["kind"] == "solo"
    assert g["name"] == "Solo Reg"


def test_ensure_solo_group_idempotent(db):
    pid = _make_player(db, "555-p202", "Idem")
    db.ensure_solo_group_for_player(pid)
    a = db.get_solo_group_id(pid)
    db.ensure_solo_group_for_player(pid)
    b = db.get_solo_group_id(pid)
    assert a == b


def test_issue_session_allowed_with_solo_group_only(db):
    pid = _make_player(db, "555-p203", "SoloIssue", credit=60)
    db.ensure_solo_group_for_player(pid)
    sid, *_ = db.issue_session_atomic(pid, "CARD-P203", 30)
    assert sid is not None


def test_one_open_visit_across_two_groups(db):
    company = db.create_company("Acme")
    g1 = db.create_group(company["id"], "T1")
    g2 = db.create_group(company["id"], "T2")
    leader = _make_player(db, "555-p204", "Lead", credit=120)
    db.add_group_member_atomic(g1["id"], leader)
    db.add_group_member_atomic(g2["id"], leader)
    db.set_group_leader(g1["id"], leader)
    db.set_group_leader(g2["id"], leader)
    db.issue_group_visit_atomic(g1["id"], 30, card_id="CARD-P204A")
    with pytest.raises(ValueError, match="open session"):
        db.issue_group_visit_atomic(g2["id"], 30, card_id="CARD-P204B")


def test_archive_hides_leaderboard_scores_by_default(db):
    company = db.create_company("LB Co")
    group = db.create_group(company["id"], "Arch Team")
    db.upsert_central_score({
        "player_id": 1, "card_id": "ARCH1", "game": "hoops",
        "played_at": "2026-06-01 12:00:00", "score": 50, "group_id": group["id"],
    })
    assert len(db.get_leaderboard(limit=50, include_archived=False)) == 1
    db.archive_group(group["id"])
    assert len(db.get_leaderboard(limit=50, include_archived=False)) == 0
    assert len(db.get_leaderboard(limit=50, include_archived=True)) == 1


def test_delete_empty_group_hard_delete(db):
    company = db.create_company("Del Co")
    group = db.create_group(company["id"], "Empty")
    result = db.delete_group(group["id"])
    assert result.get("archived") is False
    assert db.get_group(group["id"]) is None


def test_delete_group_with_scores_archives(db):
    company = db.create_company("Hist Co")
    group = db.create_group(company["id"], "Has Scores")
    db.upsert_central_score({
        "player_id": None, "card_id": "HIST1", "game": "hoops",
        "played_at": "2026-06-01 12:00:00", "score": 10, "group_id": group["id"],
    })
    result = db.delete_group(group["id"])
    assert result.get("archived") is True
    row = db.get_group(group["id"])
    assert row["archived_at"] is not None


def test_multi_group_badge_lists_all_names(db):
    company = db.create_company("Badge Co")
    team = db.create_group(company["id"], "Team X")
    pid = _make_player(db, "555-p205", "Badge Player")
    db.ensure_solo_group_for_player(pid)
    db.add_group_member_atomic(team["id"], pid)
    rows = players.list_players(db)
    row = next(r for r in rows if r["id"] == pid)
    assert "Team X" in (row["group_names"] or "")
    assert row["group_name"] == row["group_names"]


def _build_legacy_unique_player_db(db_path):
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE custom_info (
            custom_id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_num TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            public TEXT DEFAULT '1',
            time_left TEXT DEFAULT '0',
            pwd TEXT DEFAULT '',
            card_id TEXT DEFAULT ''
        );
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            name TEXT NOT NULL,
            leader_player_id INTEGER,
            created_at TEXT,
            UNIQUE(company_id, name)
        );
        CREATE TABLE group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL,
            UNIQUE(player_id)
        );
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE company_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL UNIQUE,
            joined_at TEXT
        );
        CREATE TABLE ledplay_login (id INTEGER PRIMARY KEY, name TEXT, password TEXT);
        INSERT INTO ledplay_login (name, password) VALUES ('admin', 'admin');
    """)
    con.execute("INSERT INTO companies (name, created_at) VALUES ('Acme', '2026-01-01')")
    con.execute(
        "INSERT INTO groups (company_id, name, created_at) VALUES (1, 'Team A', '2026-01-01')"
    )
    con.execute(
        "INSERT INTO custom_info (phone_num, name) VALUES ('555-legacy', 'Legacy')"
    )
    con.execute(
        "INSERT INTO group_members (group_id, player_id) VALUES (1, 1)"
    )
    con.commit()
    con.close()


@pytest.fixture
def legacy_multi_db(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_gm.sqlite"
    _build_legacy_unique_player_db(str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")
    return database_mod.Database(), str(db_path)


def test_group_members_migration_preserves_rows_idempotent(legacy_multi_db):
    db, path = legacy_multi_db
    counts_before = {}
    con = sqlite3.connect(path)
    for table in ("group_members", "groups", "custom_info", "companies"):
        counts_before[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    con.close()

    db2 = importlib.import_module("api.database").Database()
    con = sqlite3.connect(path)
    for table in counts_before:
        after = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert after == counts_before[table]
    gm = con.execute("SELECT COUNT(*) FROM group_members").fetchone()[0]
    distinct = con.execute(
        "SELECT COUNT(DISTINCT group_id || '-' || player_id) FROM group_members"
    ).fetchone()[0]
    con.close()
    assert gm == distinct

    importlib.import_module("api.database").Database()
    con = sqlite3.connect(path)
    assert con.execute("SELECT COUNT(*) FROM group_members").fetchone()[0] == gm
    con.close()
