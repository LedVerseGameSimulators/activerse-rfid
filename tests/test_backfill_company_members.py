import importlib
import sqlite3
import sys

import pytest


def _build_legacy_db_with_group_members(db_path):
    """Pre-existing DB: company_members table doesn't exist yet, but a player
    already sits in group_members under a company's group (real production shape
    before this migration existed)."""
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
            notes TEXT DEFAULT '', created_at TEXT
        );
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL,
            name TEXT NOT NULL, leader_player_id INTEGER, created_at TEXT,
            UNIQUE(company_id, name)
        );
        CREATE TABLE group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL, UNIQUE(group_id, player_id)
        );
        CREATE TABLE custom_info (
            custom_id INTEGER PRIMARY KEY AUTOINCREMENT, phone_num TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, public TEXT DEFAULT '1', time_left TEXT DEFAULT '0',
            pwd TEXT DEFAULT '', card_id TEXT DEFAULT ''
        );
    """)
    con.execute("INSERT INTO companies (name, notes, created_at) VALUES ('Acme', '', '2026-01-01')")
    con.execute(
        "INSERT INTO groups (company_id, name, leader_player_id, created_at) "
        "VALUES (1, 'Team Alpha', NULL, '2026-01-01')"
    )
    con.execute(
        "INSERT INTO custom_info (phone_num, name) VALUES ('555-0001', 'Pre-existing Player')"
    )
    con.execute("INSERT INTO group_members (group_id, player_id) VALUES (1, 1)")
    con.commit()
    con.close()


@pytest.fixture
def legacy_db_with_members(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_members.sqlite"
    _build_legacy_db_with_group_members(str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")
    return database_mod.Database()


def test_migration_backfills_company_members_for_existing_group_members(legacy_db_with_members):
    membership = legacy_db_with_members.get_company_membership(1)
    assert membership is not None
    assert membership["company_id"] == 1
