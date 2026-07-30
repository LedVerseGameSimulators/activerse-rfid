import importlib
import sqlite3
import sys

import pytest


def _build_legacy_db(db_path):
    """Simulate a pre-existing production DB with the old company_id NOT NULL schema."""
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            notes TEXT DEFAULT '',
            created_at TEXT
        );
        CREATE TABLE groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            leader_player_id INTEGER,
            created_at TEXT,
            UNIQUE(company_id, name)
        );
    """)
    con.execute("INSERT INTO companies (name, notes, created_at) VALUES ('Acme', '', '2026-01-01')")
    con.execute(
        "INSERT INTO groups (company_id, name, leader_player_id, created_at) "
        "VALUES (1, 'Acme Team', NULL, '2026-01-01')"
    )
    con.commit()
    con.close()


@pytest.fixture
def legacy_db(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite"
    _build_legacy_db(str(db_path))
    monkeypatch.setenv("DB_PATH", str(db_path))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")
    return database_mod.Database()


def test_existing_group_keeps_company_id_after_migration(legacy_db):
    groups = legacy_db.list_groups()
    assert len(groups) == 1
    assert groups[0]["name"] == "Acme Team"
    assert groups[0]["company_id"] == 1


def test_migrated_groups_table_accepts_null_company_id(legacy_db):
    group = legacy_db.create_group(None, "Birthday Party Team")
    assert group["company_id"] is None
