"""P3 audit: solo_owner_player_id backfill + partial unique index."""
import importlib
import os
import shutil
import sqlite3
import sys
import uuid

import pytest


def test_solo_owner_backfill_and_duplicate_archive(db):
    company = db.create_company(f"Co-{uuid.uuid4().hex[:6]}")
    phone = f"555-mig-{uuid.uuid4().hex[:6]}"
    db.insert_to_table_custom_tb(phone, "DupSolo", "1", "0", "", "")
    pid = db.search_custom_by_field("phone_num", phone)[0]["custom_id"]
    db.ensure_solo_group_for_player(pid)
    con = db._conn()
    try:
        cur = con.execute(
            "INSERT INTO groups (company_id, name, leader_player_id, created_at, kind) "
            "VALUES (?, ?, ?, ?, 'solo')",
            (company["id"], "Solo duplicate", pid, "2099-01-01 00:00:00"),
        )
        gid2 = cur.lastrowid
        con.execute(
            "INSERT OR IGNORE INTO group_members (group_id, player_id) VALUES (?, ?)",
            (gid2, pid),
        )
        db._migrate_solo_group_owner(con)
        con.commit()
    finally:
        con.close()
    rows = db._execute(
        "SELECT id, solo_owner_player_id, archived_at FROM groups "
        "WHERE kind = 'solo' AND solo_owner_player_id = ? ORDER BY id",
        (pid,),
        fetch="all",
    )
    active = [r for r in rows if not r["archived_at"]]
    assert len(active) == 1
    assert active[0]["solo_owner_player_id"] == pid


@pytest.mark.skipif(
    not os.path.isfile("/Users/apple/activerse_final_changes/activerse-rfid/data/rfid.sqlite"),
    reason="no production sqlite copy in workspace",
)
def test_migration_idempotent_on_real_db_copy(tmp_path, monkeypatch):
    src = "/Users/apple/activerse_final_changes/activerse-rfid/data/rfid.sqlite"
    dest = tmp_path / "rfid-migrate-copy.sqlite"
    shutil.copy2(src, dest)
    monkeypatch.setenv("DB_PATH", str(dest))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")

    def row_counts(path):
        con = sqlite3.connect(path)
        return {
            "group_members": con.execute("SELECT COUNT(*) FROM group_members").fetchone()[0],
            "custom_info": con.execute("SELECT COUNT(*) FROM custom_info").fetchone()[0],
            "central_scores": con.execute("SELECT COUNT(*) FROM central_scores").fetchone()[0],
            "player_sessions": con.execute("SELECT COUNT(*) FROM player_sessions").fetchone()[0],
        }

    database_mod.Database()
    after_first = row_counts(dest)
    database_mod.Database()
    after_second = row_counts(dest)
    assert after_first == after_second
