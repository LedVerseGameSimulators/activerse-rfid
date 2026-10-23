"""
SQLite/MySQL database wrapper for Activerse RFID server.
Ports SQL from ledplayserver db_operation.py; adds new session/score tables.
"""
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .config import DB_PATH

_USE_MYSQL = bool(os.getenv("MYSQL_HOST"))


class Database:
    """Thread-safe DB access. Dev = SQLite; prod = MySQL via env vars."""

    def __init__(self):
        self._lock = threading.Lock()
        if _USE_MYSQL:
            self._init_mysql()
        else:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            self._ensure_tables()
            logger.info(f"SQLite database ready at {DB_PATH}")

    # ── Connection ────────────────────────────────────────────────────────

    def _conn(self):
        con = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def _init_mysql(self):
        import mysql.connector
        self._mysql = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            passwd=os.getenv("MYSQL_PASS", "root"),
            database=os.getenv("MYSQL_DB", "ledplaydb"),
        )
        logger.info("MySQL database connected")

    def _execute(self, sql: str, params: tuple = (), fetch: str = "none"):
        """Run SQL. Uses ? placeholders (SQLite)."""
        with self._lock:
            con = self._conn()
            try:
                cur = con.execute(sql, params)
                if fetch == "all":
                    rows = cur.fetchall()
                elif fetch == "one":
                    rows = cur.fetchone()
                else:
                    rows = None
                con.commit()
                return rows
            finally:
                con.close()

    def _executemany_return_id(self, sql: str, params: tuple) -> int:
        with self._lock:
            con = self._conn()
            try:
                cur = con.execute(sql, params)
                con.commit()
                return cur.lastrowid
            finally:
                con.close()

    def _rowcount(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            con = self._conn()
            try:
                cur = con.execute(sql, params)
                con.commit()
                return cur.rowcount
            finally:
                con.close()

    # ── Table creation ────────────────────────────────────────────────────

    def _ensure_tables(self):
        with self._lock:
            con = self._conn()
            try:
                # Must run before CREATE IF NOT EXISTS central_scores, otherwise an
                # interrupted rebuild (only central_scores_v2 left) would spawn an
                # empty central_scores and the migrate step would drop v2.
                self._recover_central_scores_v2(con)
                self._recover_groups_v2(con)
                self._recover_group_members_v2(con)
                # Legacy tables (same names/columns as original MySQL)
                con.executescript("""
                    CREATE TABLE IF NOT EXISTS custom_info (
                        custom_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                        phone_num   TEXT UNIQUE NOT NULL,
                        name        TEXT NOT NULL,
                        public      TEXT DEFAULT '1',
                        time_left   TEXT DEFAULT '0',
                        pwd         TEXT DEFAULT '',
                        card_id     TEXT DEFAULT ''
                    );

                    CREATE TABLE IF NOT EXISTS recharge_record (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        custom_id   TEXT,
                        money       TEXT,
                        game_time   TEXT,
                        date        TEXT
                    );

                    CREATE TABLE IF NOT EXISTS bind_card_record (
                        id            INTEGER PRIMARY KEY AUTOINCREMENT,
                        custom_phone  TEXT,
                        action        TEXT,
                        card_id       TEXT,
                        date          TEXT
                    );

                    CREATE TABLE IF NOT EXISTS ledplay_login (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        name      TEXT,
                        password  TEXT
                    );

                    CREATE TABLE IF NOT EXISTS player_sessions (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id    INTEGER,
                        card_id      TEXT,
                        issued_at    TEXT,
                        expiry_at    TEXT,
                        duration_min INTEGER,
                        closed_at    TEXT,
                        notes        TEXT
                    );

                    CREATE TABLE IF NOT EXISTS session_adjustments (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id  INTEGER,
                        delta_min   INTEGER,
                        reason      TEXT,
                        adjusted_at TEXT,
                        adjusted_by TEXT
                    );

                    CREATE TABLE IF NOT EXISTS play_time_events (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id   INTEGER NOT NULL,
                        session_id  INTEGER,
                        group_id    INTEGER,
                        company_id  INTEGER,
                        minutes     REAL NOT NULL,
                        source      TEXT NOT NULL,
                        earned_at   TEXT NOT NULL,
                        notes       TEXT DEFAULT ''
                    );
                    CREATE INDEX IF NOT EXISTS idx_play_time_player
                        ON play_time_events(player_id, earned_at);
                    CREATE INDEX IF NOT EXISTS idx_play_time_session
                        ON play_time_events(session_id);

                    CREATE TABLE IF NOT EXISTS session_roster (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id  INTEGER NOT NULL,
                        player_id   INTEGER NOT NULL,
                        UNIQUE(session_id, player_id)
                    );

                    CREATE TABLE IF NOT EXISTS central_team_scores (
                        id             INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id     INTEGER,
                        card_id        TEXT,
                        player_slot    INTEGER,
                        game           TEXT,
                        level          TEXT,
                        end_level      TEXT,
                        level_file     TEXT,
                        end_level_file TEXT,
                        score          REAL,
                        final_score    REAL,
                        member_count   INTEGER,
                        members_json   TEXT,
                        life           INTEGER,
                        lives_start    INTEGER,
                        result         INTEGER,
                        time_used      REAL,
                        levels_cleared INTEGER,
                        difficulty     TEXT,
                        started_at     TEXT,
                        played_at      TEXT,
                        polled_at      TEXT,
                        UNIQUE(game, card_id, player_slot, level, played_at, score)
                    );

                    CREATE TABLE IF NOT EXISTS central_scores (
                        id             INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id      INTEGER,
                        card_id        TEXT,
                        player_slot    INTEGER,   -- 1 or 2 (which player this row is)
                        session_id     INTEGER,
                        team_score_id  INTEGER,
                        game           TEXT,
                        level          TEXT,
                        end_level      TEXT,
                        level_file     TEXT,
                        end_level_file TEXT,
                        score          REAL,      -- this player's RAW score
                        final_score    REAL,      -- this player's NORMALIZED score
                        life           INTEGER,
                        lives_start    INTEGER,
                        result         INTEGER,
                        time_used      REAL,
                        levels_cleared INTEGER,
                        difficulty     TEXT,
                        started_at     TEXT,
                        played_at      TEXT,
                        polled_at      TEXT,
                        UNIQUE(game, card_id, player_id, level, played_at, score)
                    );

                    CREATE TABLE IF NOT EXISTS game_health (
                        game            TEXT PRIMARY KEY,
                        status          TEXT,
                        last_checked    TEXT,
                        active_game_id  TEXT
                    );

                    CREATE TABLE IF NOT EXISTS poll_cursors (
                        game     TEXT PRIMARY KEY,
                        last_ts  TEXT
                    );

                    CREATE TABLE IF NOT EXISTS settings (
                        key   TEXT PRIMARY KEY,
                        value TEXT
                    );

                    CREATE TABLE IF NOT EXISTS game_settings_pushed (
                        game               TEXT PRIMARY KEY,
                        default_difficulty TEXT,
                        session_minutes    INTEGER,
                        pushed_at          TEXT
                    );

                    CREATE TABLE IF NOT EXISTS companies (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        name        TEXT UNIQUE NOT NULL,
                        notes       TEXT DEFAULT '',
                        created_at  TEXT
                    );

                    CREATE TABLE IF NOT EXISTS groups (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id        INTEGER,
                        name              TEXT NOT NULL,
                        leader_player_id  INTEGER,
                        created_at        TEXT,
                        archived_at       TEXT,
                        kind                  TEXT DEFAULT 'team',
                        solo_owner_player_id  INTEGER,
                        UNIQUE(company_id, name)
                    );

                    CREATE TABLE IF NOT EXISTS group_members (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id   INTEGER NOT NULL,
                        player_id  INTEGER NOT NULL,
                        UNIQUE(group_id, player_id)
                    );

                    CREATE TABLE IF NOT EXISTS company_members (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id  INTEGER NOT NULL,
                        player_id   INTEGER NOT NULL UNIQUE,
                        joined_at   TEXT,
                        FOREIGN KEY (company_id) REFERENCES companies(id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_company_members_company
                        ON company_members(company_id);
                """)
                # Idempotent ALTERs for central_scores (existing DBs upgrading
                # from the pre-per-player schema).
                for _col, _typ in (("player_slot", "INTEGER"), ("end_level", "TEXT"),
                                   ("level_file", "TEXT"), ("end_level_file", "TEXT"),
                                   ("final_score", "REAL"), ("lives_start", "INTEGER"),
                                   ("levels_cleared", "INTEGER"), ("difficulty", "TEXT"),
                                   ("started_at", "TEXT"), ("team_score_id", "INTEGER"),
                                   ("company_id", "INTEGER"), ("group_id", "INTEGER")):
                    try:
                        con.execute(f"ALTER TABLE central_scores ADD COLUMN {_col} {_typ}")
                    except sqlite3.OperationalError:
                        pass
                for _col, _typ in (("company_id", "INTEGER"), ("group_id", "INTEGER")):
                    try:
                        con.execute(f"ALTER TABLE player_sessions ADD COLUMN {_col} {_typ}")
                    except sqlite3.OperationalError:
                        pass
                for _col in ("company_id", "group_id", "level_file", "end_level_file", "end_level"):
                    try:
                        con.execute(f"ALTER TABLE central_team_scores ADD COLUMN {_col} "
                                    f"{'INTEGER' if _col in ('company_id', 'group_id') else 'TEXT'}")
                    except sqlite3.OperationalError:
                        pass
                for _col, _typ in (
                    ("play_mode", "TEXT"),
                    ("roster_size_at_play", "INTEGER"),
                    ("two_card_play", "INTEGER DEFAULT 0"),
                    ("match_key", "TEXT"),
                    ("opponent_group_id", "INTEGER"),
                    ("opponent_card_id", "TEXT"),
                ):
                    for _table in ("central_team_scores", "central_scores"):
                        try:
                            con.execute(f"ALTER TABLE {_table} ADD COLUMN {_col} {_typ}")
                        except sqlite3.OperationalError:
                            pass
                # Optional columns on custom_info
                for col, typ in (("email", "TEXT"), ("age", "INTEGER"), ("notes", "TEXT"),
                                ("credit_balance", "REAL DEFAULT 0")):
                    try:
                        con.execute(f"ALTER TABLE custom_info ADD COLUMN {col} {typ}")
                    except sqlite3.OperationalError:
                        pass
                for _col, _typ in (
                    ("adjustment_mode", "TEXT DEFAULT 'free_clock'"),
                    ("balance_delta_min", "REAL DEFAULT 0"),
                ):
                    try:
                        con.execute(
                            f"ALTER TABLE session_adjustments ADD COLUMN {_col} {_typ}"
                        )
                    except sqlite3.OperationalError:
                        pass
                # Rebuild central_scores unique key so team split shares
                # (same card/score, different player_id) do not collapse.
                self._migrate_central_scores_unique(con)
                # Rebuild groups so company_id can be NULL (walk-in groups).
                self._migrate_groups_nullable_company(con)
                # Rebuild group_members for multi-group membership (drop UNIQUE(player_id)).
                self._migrate_group_members_multi_group(con)
                for _col, _typ in (
                    ("archived_at", "TEXT"),
                    ("kind", "TEXT DEFAULT 'team'"),
                    ("solo_owner_player_id", "INTEGER"),
                ):
                    try:
                        con.execute(f"ALTER TABLE groups ADD COLUMN {_col} {_typ}")
                    except sqlite3.OperationalError:
                        pass
                try:
                    con.execute(
                        "CREATE INDEX IF NOT EXISTS idx_groups_archived ON groups(archived_at)"
                    )
                except sqlite3.OperationalError:
                    pass
                self._migrate_solo_group_owner(con)
                # Corporate group affiliation before walk-in backfill (P2).
                con.execute(
                    "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
                    "SELECT g.company_id, gm.player_id, ? FROM group_members gm "
                    "JOIN groups g ON g.id = gm.group_id WHERE g.company_id IS NOT NULL",
                    (self._now_iso(),),
                )
                self._bootstrap_p2_org(con)
                self._backfill_day_one_roster_join_ledger(con)
                # P4a: tournaments + leaderboard indexes
                con.executescript("""
                    CREATE TABLE IF NOT EXISTS tournaments (
                      id          INTEGER PRIMARY KEY AUTOINCREMENT,
                      name        TEXT NOT NULL,
                      type        TEXT NOT NULL CHECK (type IN ('solo','team')),
                      scope       TEXT NOT NULL CHECK (scope IN ('global','company')),
                      company_id  INTEGER,
                      starts_at   TEXT,
                      ends_at     TEXT,
                      status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','archived')),
                      system_key  TEXT UNIQUE,
                      rules_json  TEXT DEFAULT '{}',
                      created_at  TEXT,
                      updated_at  TEXT,
                      created_by  TEXT DEFAULT '',
                      CHECK ((scope='global' AND company_id IS NULL) OR (scope='company' AND company_id IS NOT NULL)),
                      FOREIGN KEY (company_id) REFERENCES companies(id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_tournaments_lookup ON tournaments(type, scope, status);
                    CREATE INDEX IF NOT EXISTS idx_tournaments_company ON tournaments(company_id);
                    CREATE INDEX IF NOT EXISTS idx_cs_played_at    ON central_scores(played_at);
                    CREATE INDEX IF NOT EXISTS idx_cs_player       ON central_scores(player_id);
                    CREATE INDEX IF NOT EXISTS idx_cs_group        ON central_scores(group_id);
                    CREATE INDEX IF NOT EXISTS idx_cs_company      ON central_scores(company_id, played_at);
                    CREATE INDEX IF NOT EXISTS idx_cs_session      ON central_scores(session_id);
                    CREATE INDEX IF NOT EXISTS idx_cts_played_at   ON central_team_scores(played_at);
                    CREATE INDEX IF NOT EXISTS idx_cts_group       ON central_team_scores(group_id);
                    CREATE INDEX IF NOT EXISTS idx_cts_company     ON central_team_scores(company_id, played_at);
                    CREATE INDEX IF NOT EXISTS idx_cts_session     ON central_team_scores(session_id);
                    CREATE INDEX IF NOT EXISTS idx_cts_match_key   ON central_team_scores(match_key);
                    CREATE INDEX IF NOT EXISTS idx_pte_company     ON play_time_events(company_id, earned_at);
                    CREATE INDEX IF NOT EXISTS idx_pte_group       ON play_time_events(group_id);
                    CREATE INDEX IF NOT EXISTS idx_ps_group        ON player_sessions(group_id);
                    CREATE INDEX IF NOT EXISTS idx_ps_player       ON player_sessions(player_id, issued_at);
                """)
                self._seed_legacy_tournaments(con)
                # Seed default admin if empty
                row = con.execute("SELECT COUNT(*) AS c FROM ledplay_login").fetchone()
                if row["c"] == 0:
                    con.execute(
                        "INSERT INTO ledplay_login (name, password) VALUES (?, ?)",
                        ("admin", os.getenv("ADMIN_PASSWORD", "admin")),
                    )
                # Seed game_health rows
                for game in ("hoops", "laser", "climb", "grid", "led_hex"):
                    con.execute(
                        "INSERT OR IGNORE INTO game_health (game, status) VALUES (?, 'down')",
                        (game,),
                    )
                # Seed default settings (money/time ratios + topup limits)
                for k, v in (("money_per_minute", "25"), ("min_topup_minutes", "10"),
                            ("max_topup_minutes", "600")):
                    con.execute(
                        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
                    )
                con.commit()
            finally:
                con.close()

    @staticmethod
    def _table_names(con):
        return {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    @staticmethod
    def _recover_central_scores_v2(con):
        """If a prior UNIQUE rebuild left only central_scores_v2, rename it back."""
        names = Database._table_names(con)
        if "central_scores_v2" in names and "central_scores" not in names:
            con.execute("ALTER TABLE central_scores_v2 RENAME TO central_scores")

    @staticmethod
    def _migrate_central_scores_unique(con):
        """Ensure UNIQUE includes player_id (idempotent for fresh + old DBs)."""
        names = Database._table_names(con)
        # Leftover v2 from a failed rebuild while old central_scores still present.
        if "central_scores_v2" in names and "central_scores" in names:
            con.execute("DROP TABLE central_scores_v2")

        row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='central_scores'"
        ).fetchone()
        if not row or not row["sql"]:
            return
        norm = "".join(row["sql"].split())
        if "UNIQUE(game,card_id,player_id,level,played_at,score)" in norm:
            return
        if "UNIQUE(game,card_id,level,played_at,score)" not in norm:
            return

        con.executescript("""
            CREATE TABLE central_scores_v2 (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id      INTEGER,
                card_id        TEXT,
                player_slot    INTEGER,
                session_id     INTEGER,
                team_score_id  INTEGER,
                game           TEXT,
                level          TEXT,
                end_level      TEXT,
                score          REAL,
                final_score    REAL,
                life           INTEGER,
                lives_start    INTEGER,
                result         INTEGER,
                time_used      REAL,
                levels_cleared INTEGER,
                difficulty     TEXT,
                started_at     TEXT,
                played_at      TEXT,
                polled_at      TEXT,
                UNIQUE(game, card_id, player_id, level, played_at, score)
            );
            INSERT OR IGNORE INTO central_scores_v2 (
                id, player_id, card_id, player_slot, session_id, team_score_id,
                game, level, end_level, score, final_score, life, lives_start,
                result, time_used, levels_cleared, difficulty, started_at,
                played_at, polled_at
            )
            SELECT
                id, player_id, card_id, player_slot, session_id,
                team_score_id, game, level, end_level, score, final_score, life, lives_start,
                result, time_used, levels_cleared, difficulty, started_at,
                played_at, polled_at
            FROM central_scores;
            DROP TABLE central_scores;
            ALTER TABLE central_scores_v2 RENAME TO central_scores;
        """)

    @staticmethod
    def _recover_groups_v2(con):
        """If a prior nullable-company_id rebuild left only groups_v2, rename it back."""
        names = Database._table_names(con)
        if "groups_v2" in names and "groups" not in names:
            con.execute("ALTER TABLE groups_v2 RENAME TO groups")

    @staticmethod
    def _migrate_groups_nullable_company(con):
        """Ensure groups.company_id allows NULL (walk-in groups with no company)."""
        names = Database._table_names(con)
        # Leftover v2 from a failed rebuild while old groups table still present.
        if "groups_v2" in names and "groups" in names:
            con.execute("DROP TABLE groups_v2")

        row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'"
        ).fetchone()
        if not row or not row["sql"]:
            return
        norm = "".join(row["sql"].split())
        if "company_idINTEGERNOTNULL" not in norm:
            return  # already nullable

        con.executescript("""
            CREATE TABLE groups_v2 (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id        INTEGER,
                name              TEXT NOT NULL,
                leader_player_id  INTEGER,
                created_at        TEXT,
                UNIQUE(company_id, name)
            );
            INSERT OR IGNORE INTO groups_v2 (
                id, company_id, name, leader_player_id, created_at
            )
            SELECT id, company_id, name, leader_player_id, created_at
            FROM groups;
            DROP TABLE groups;
            ALTER TABLE groups_v2 RENAME TO groups;
        """)

    @staticmethod
    def _recover_group_members_v2(con):
        """If a prior unique-player rebuild left only group_members_v2, rename it back."""
        names = Database._table_names(con)
        if "group_members_v2" in names and "group_members" not in names:
            con.execute("ALTER TABLE group_members_v2 RENAME TO group_members")

    @staticmethod
    def _migrate_group_members_multi_group(con):
        """Drop UNIQUE(player_id); keep UNIQUE(group_id, player_id) only (P2)."""
        names = Database._table_names(con)
        if "group_members_v2" in names and "group_members" in names:
            con.execute("DROP TABLE group_members_v2")

        row = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='group_members'"
        ).fetchone()
        if not row or not row["sql"]:
            return
        norm = "".join(row["sql"].split())
        if "UNIQUE(player_id)" not in norm:
            return  # already multi-group

        con.executescript("""
            CREATE TABLE group_members_v2 (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id   INTEGER NOT NULL,
                player_id  INTEGER NOT NULL,
                UNIQUE(group_id, player_id)
            );
            INSERT OR IGNORE INTO group_members_v2 (id, group_id, player_id)
            SELECT id, group_id, player_id FROM group_members;
            DROP TABLE group_members;
            ALTER TABLE group_members_v2 RENAME TO group_members;
        """)

    def _migrate_solo_group_owner(self, con):
        """One active solo group per player: solo_owner_player_id + partial unique index."""
        try:
            con.execute("ALTER TABLE groups ADD COLUMN solo_owner_player_id INTEGER")
        except sqlite3.OperationalError:
            pass
        now = self._now_iso()
        dup_leaders = con.execute(
            "SELECT leader_player_id FROM groups "
            "WHERE kind = 'solo' AND archived_at IS NULL AND leader_player_id IS NOT NULL "
            "GROUP BY leader_player_id HAVING COUNT(*) > 1"
        ).fetchall()
        for row in dup_leaders:
            pid = int(row["leader_player_id"])
            group_rows = con.execute(
                "SELECT id FROM groups WHERE kind = 'solo' AND leader_player_id = ? "
                "AND archived_at IS NULL ORDER BY created_at ASC, id ASC",
                (pid,),
            ).fetchall()
            for extra in group_rows[1:]:
                con.execute(
                    "UPDATE groups SET archived_at = ? WHERE id = ?",
                    (now, int(extra["id"])),
                )
        solos = con.execute(
            "SELECT id, leader_player_id FROM groups WHERE kind = 'solo'"
        ).fetchall()
        for g in solos:
            gid = int(g["id"])
            owner = g["leader_player_id"]
            if not owner:
                mem = con.execute(
                    "SELECT player_id FROM group_members WHERE group_id = ? LIMIT 1",
                    (gid,),
                ).fetchone()
                if mem:
                    owner = mem["player_id"]
            if owner and not con.execute(
                "SELECT solo_owner_player_id FROM groups WHERE id = ?", (gid,)
            ).fetchone()["solo_owner_player_id"]:
                con.execute(
                    "UPDATE groups SET solo_owner_player_id = ? WHERE id = ?",
                    (int(owner), gid),
                )
        dup_owners = con.execute(
            "SELECT solo_owner_player_id FROM groups "
            "WHERE kind = 'solo' AND solo_owner_player_id IS NOT NULL "
            "AND archived_at IS NULL "
            "GROUP BY solo_owner_player_id HAVING COUNT(*) > 1"
        ).fetchall()
        for row in dup_owners:
            pid = int(row["solo_owner_player_id"])
            group_rows = con.execute(
                "SELECT id FROM groups WHERE kind = 'solo' "
                "AND solo_owner_player_id = ? AND archived_at IS NULL "
                "ORDER BY created_at ASC, id ASC",
                (pid,),
            ).fetchall()
            for extra in group_rows[1:]:
                con.execute(
                    "UPDATE groups SET archived_at = ? WHERE id = ?",
                    (now, int(extra["id"])),
                )
        con.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_groups_solo_owner_unique "
            "ON groups(solo_owner_player_id) "
            "WHERE kind = 'solo' AND solo_owner_player_id IS NOT NULL "
            "AND archived_at IS NULL"
        )

    def _bootstrap_p2_org(self, con):
        """Walk-in company setting + backfill company/solo groups (idempotent)."""
        walk_id = self._ensure_walk_in_company_row(con)
        self._backfill_walk_in_members(con, walk_id)
        self._backfill_solo_groups(con, walk_id)

    @staticmethod
    def _seed_legacy_tournaments(con):
        """Idempotent legacy global tournaments + active settings (P4a)."""
        now = Database._now_iso()
        con.execute(
            "INSERT OR IGNORE INTO tournaments "
            "(name, type, scope, company_id, starts_at, ends_at, status, system_key, "
            "created_at, updated_at, created_by) VALUES "
            "('All time (legacy) — Solo', 'solo', 'global', NULL, NULL, NULL, 'active', "
            "'legacy_solo', ?, ?, 'system'), "
            "('All time (legacy) — Team', 'team', 'global', NULL, NULL, NULL, 'active', "
            "'legacy_team', ?, ?, 'system')",
            (now, now, now, now),
        )
        con.execute(
            "INSERT OR IGNORE INTO settings (key, value) "
            "SELECT 'active_global_solo_tournament_id', CAST(id AS TEXT) "
            "FROM tournaments WHERE system_key='legacy_solo'"
        )
        con.execute(
            "INSERT OR IGNORE INTO settings (key, value) "
            "SELECT 'active_global_team_tournament_id', CAST(id AS TEXT) "
            "FROM tournaments WHERE system_key='legacy_team'"
        )

    def _ensure_walk_in_company_row(self, con) -> int:
        row = con.execute(
            "SELECT value FROM settings WHERE key = 'walk_in_company_id'"
        ).fetchone()
        if row and row["value"]:
            try:
                cid = int(row["value"])
            except (TypeError, ValueError):
                cid = None
            else:
                if con.execute("SELECT 1 FROM companies WHERE id = ?", (cid,)).fetchone():
                    return cid
        existing = con.execute(
            "SELECT id FROM companies WHERE lower(name) = lower(?)", ("Walk-in",)
        ).fetchone()
        if existing:
            cid = int(existing["id"])
        else:
            cur = con.execute(
                "INSERT INTO companies (name, notes, created_at) VALUES (?, ?, ?)",
                ("Walk-in", "", self._now_iso()),
            )
            cid = int(cur.lastrowid)
        con.execute(
            "INSERT INTO settings (key, value) VALUES ('walk_in_company_id', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(cid),),
        )
        return cid

    def get_walk_in_company_id(self) -> int:
        with self._lock:
            con = self._conn()
            try:
                return self._ensure_walk_in_company_row(con)
            finally:
                con.close()

    def _backfill_walk_in_members(self, con, walk_in_id: int):
        con.execute(
            "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
            "SELECT ?, ci.custom_id, ? FROM custom_info ci "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM company_members cm WHERE cm.player_id = ci.custom_id"
            ")",
            (walk_in_id, self._now_iso()),
        )

    def _create_solo_group_locked(self, con, player_id: int, player_name: str, company_id: int) -> int:
        existing = con.execute(
            "SELECT g.id FROM groups g "
            "JOIN group_members gm ON gm.group_id = g.id "
            "WHERE gm.player_id = ? AND g.kind = 'solo' LIMIT 1",
            (player_id,),
        ).fetchone()
        if existing:
            return int(existing["id"])
        base_name = (player_name or f"Player {player_id}").strip()
        solo_name = base_name
        if con.execute(
            "SELECT 1 FROM groups WHERE company_id = ? AND lower(name) = lower(?)",
            (company_id, solo_name),
        ).fetchone():
            solo_name = f"{base_name} ({player_id})"
        cur = con.execute(
            "INSERT INTO groups (company_id, name, leader_player_id, created_at, kind, "
            "solo_owner_player_id) VALUES (?, ?, ?, ?, 'solo', ?)",
            (company_id, solo_name, player_id, self._now_iso(), player_id),
        )
        gid = int(cur.lastrowid)
        con.execute(
            "INSERT OR IGNORE INTO group_members (group_id, player_id) VALUES (?, ?)",
            (gid, player_id),
        )
        return gid

    def _backfill_solo_groups(self, con, walk_in_id: int):
        rows = con.execute(
            "SELECT ci.custom_id, ci.name FROM custom_info ci "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM group_members gm JOIN groups g ON g.id = gm.group_id "
            "  WHERE gm.player_id = ci.custom_id AND g.kind = 'solo'"
            ")"
        ).fetchall()
        for row in rows:
            self._create_solo_group_locked(
                con, int(row["custom_id"]), row["name"], walk_in_id
            )

    def ensure_player_org_on_register(self, player_id: int):
        """Walk-in company + solo group (idempotent)."""
        with self._lock:
            con = self._conn()
            try:
                walk_id = self._ensure_walk_in_company_row(con)
                con.execute(
                    "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
                    "VALUES (?, ?, ?)",
                    (walk_id, player_id, self._now_iso()),
                )
                prow = con.execute(
                    "SELECT name FROM custom_info WHERE custom_id = ?", (player_id,)
                ).fetchone()
                name = prow["name"] if prow else f"Player {player_id}"
                self._create_solo_group_locked(con, player_id, name, walk_id)
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def ensure_solo_group_for_player(self, player_id: int):
        """Solo group only (import / linked players)."""
        with self._lock:
            con = self._conn()
            try:
                walk_id = self._ensure_walk_in_company_row(con)
                con.execute(
                    "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
                    "VALUES (?, ?, ?)",
                    (walk_id, player_id, self._now_iso()),
                )
                prow = con.execute(
                    "SELECT name FROM custom_info WHERE custom_id = ?", (player_id,)
                ).fetchone()
                name = prow["name"] if prow else f"Player {player_id}"
                self._create_solo_group_locked(con, player_id, name, walk_id)
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def get_solo_group_id(self, player_id: int) -> Optional[int]:
        row = self._execute(
            "SELECT g.id FROM groups g "
            "JOIN group_members gm ON gm.group_id = g.id "
            "WHERE gm.player_id = ? AND g.kind = 'solo' LIMIT 1",
            (player_id,),
            fetch="one",
        )
        return int(row["id"]) if row else None

    def list_groups_for_player(self, player_id: int, include_archived: bool = False):
        clauses = ["gm.player_id = ?"]
        params: list = [player_id]
        if not include_archived:
            clauses.append("(g.archived_at IS NULL)")
        where = " AND ".join(clauses)
        rows = self._execute(
            f"SELECT g.*, c.name AS company_name FROM group_members gm "
            f"JOIN groups g ON g.id = gm.group_id "
            f"LEFT JOIN companies c ON c.id = g.company_id "
            f"WHERE {where} ORDER BY g.kind = 'solo' DESC, g.name",
            tuple(params),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _row_to_dict(row) -> Optional[dict]:
        if row is None:
            return None
        return dict(row)

    # ── Ported from db_operation.py ───────────────────────────────────────

    def search_custom_by_field(self, field: str, value: Any):
        sql = f"SELECT * FROM custom_info WHERE {field} = ?"
        rows = self._execute(sql, (value,), fetch="all")
        return [dict(r) for r in rows] if rows else []

    def search_custom_tb_by_id(self, custom_id):
        rows = self._execute(
            "SELECT * FROM custom_info WHERE custom_id = ?", (custom_id,), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    def search_custom_tb_by_name_or_phone(self, name: str, phone: str):
        rows = self._execute(
            "SELECT * FROM custom_info WHERE name = ? OR phone_num = ?",
            (name, phone),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def insert_to_table_custom_tb(self, phone, name, rank, time_left, pwd, card_id=""):
        return self._rowcount(
            "INSERT INTO custom_info (phone_num, name, public, time_left, pwd, card_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (phone, name, rank, time_left, pwd, card_id),
        )

    def insert_to_table_recharge_record(self, custom_id, money, game_time, date):
        return self._rowcount(
            "INSERT INTO recharge_record (custom_id, money, game_time, date) VALUES (?, ?, ?, ?)",
            (custom_id, money, game_time, date),
        )

    def insert_to_table_bind_card_record(self, phone, action, card_id, date):
        return self._rowcount(
            "INSERT INTO bind_card_record (custom_phone, action, card_id, date) VALUES (?, ?, ?, ?)",
            (phone, action, card_id, date),
        )

    def update_custom_tb(self, custom_id, phone_num, name, public, time_left):
        return self._rowcount(
            "UPDATE custom_info SET phone_num=?, name=?, public=?, time_left=? WHERE custom_id=?",
            (phone_num, name, public, time_left, custom_id),
        )

    def update_custom_value(self, custom_id, flag, value):
        sql = f"UPDATE custom_info SET {flag} = ? WHERE custom_id = ?"
        return self._rowcount(sql, (value, custom_id))

    def get_credit_balance(self, player_id: int) -> float:
        row = self._execute(
            "SELECT credit_balance FROM custom_info WHERE custom_id = ?",
            (player_id,), fetch="one"
        )
        return float(row["credit_balance"]) if row and row["credit_balance"] is not None else 0.0

    def add_credit(self, player_id: int, minutes: float, amount_money: float,
                   performed_by: str = ""):
        self._execute(
            "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) + ? "
            "WHERE custom_id = ?",
            (minutes, player_id),
        )
        str_time = self._now_iso()
        self.insert_to_table_recharge_record(str(player_id), str(amount_money), str(minutes), str_time)
        return self.get_credit_balance(player_id)

    def deduct_credit(self, player_id: int, minutes: float):
        self._execute(
            "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) - ? "
            "WHERE custom_id = ?",
            (minutes, player_id),
        )
        return self.get_credit_balance(player_id)

    def search_from_table(self, table: str):
        rows = self._execute(f"SELECT * FROM {table}", fetch="all")
        return [tuple(dict(r).values()) for r in rows] if rows else []

    def delete_table_data(self, table: str):
        self._execute(f"DELETE FROM {table}")

    def delete_player(self, player_id: int):
        """Remove player row and org links; archive or drop solo group as needed."""
        with self._lock:
            con = self._conn()
            try:
                row = con.execute(
                    "SELECT custom_id FROM custom_info WHERE custom_id = ?", (player_id,)
                ).fetchone()
                if not row:
                    raise ValueError("Player not found")

                now = self._now_iso()
                busy = con.execute(
                    "SELECT ps.id FROM session_roster sr "
                    "JOIN player_sessions ps ON ps.id = sr.session_id "
                    "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                    "LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if busy:
                    raise ValueError(
                        f"Player has an active visit (session #{busy['id']}); close it first."
                    )
                own = con.execute(
                    "SELECT id FROM player_sessions WHERE player_id = ? "
                    "AND closed_at IS NULL AND expiry_at > ? LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if own:
                    raise ValueError(
                        f"Player has an open payer session #{own['id']}; close it first."
                    )

                led = con.execute(
                    "SELECT g.id, g.name FROM groups g "
                    "WHERE g.leader_player_id = ? AND COALESCE(g.kind, 'team') != 'solo' "
                    "AND g.archived_at IS NULL LIMIT 1",
                    (player_id,),
                ).fetchone()
                if led:
                    raise ValueError(
                        f"Player is the leader of team '{led['name']}'; assign a new leader first."
                    )

                solo_row = con.execute(
                    "SELECT g.id FROM groups g "
                    "JOIN group_members gm ON gm.group_id = g.id "
                    "WHERE gm.player_id = ? AND g.kind = 'solo' LIMIT 1",
                    (player_id,),
                ).fetchone()
                solo_gid = int(solo_row["id"]) if solo_row else None

                con.execute("DELETE FROM group_members WHERE player_id = ?", (player_id,))

                if solo_gid is not None:
                    if self._group_has_history_conn(con, solo_gid):
                        self._archive_group_locked(con, solo_gid, allow_solo=True)
                    else:
                        con.execute("DELETE FROM groups WHERE id = ?", (solo_gid,))

                con.execute("DELETE FROM company_members WHERE player_id = ?", (player_id,))
                con.execute("DELETE FROM custom_info WHERE custom_id = ?", (player_id,))
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def search_recharge_tb_by_id(self, custom_id: int):
        rows = self._execute(
            "SELECT * FROM recharge_record WHERE custom_id = ? ORDER BY date DESC",
            (str(custom_id),), fetch="all"
        )
        return [dict(r) for r in rows] if rows else []

    def insert_to_table_login(self, account, password):
        return self._rowcount(
            "INSERT INTO ledplay_login (name, password) VALUES (?, ?)",
            (account, password),
        )

    def list_all_custom_info(self):
        rows = self._execute("SELECT * FROM custom_info ORDER BY custom_id", fetch="all")
        return [dict(r) for r in rows] if rows else []

    def search_custom_multi(self, q: str):
        like = f"%{q}%"
        rows = self._execute(
            "SELECT * FROM custom_info WHERE phone_num LIKE ? OR name LIKE ? OR card_id LIKE ? "
            "ORDER BY custom_id",
            (like, like, like),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    # ── New session/score methods ─────────────────────────────────────────

    @staticmethod
    def _minutes_remaining_clock(expiry_at: str) -> float:
        expiry = datetime.strptime(expiry_at, "%Y-%m-%d %H:%M:%S")
        delta = (expiry - datetime.now()).total_seconds() / 60
        return max(0.0, round(delta, 1))

    @staticmethod
    def _elapsed_minutes_since(issued_at: str, cap_at: float) -> float:
        issued = datetime.strptime(issued_at, "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.now() - issued).total_seconds() / 60
        elapsed = max(0.0, round(elapsed, 1))
        return min(elapsed, max(0.0, cap_at))

    def _session_paid_total(self, con, session_id: int, duration_min: float) -> float:
        """Wallet minutes charged for this visit (free_clock extensions excluded)."""
        row = con.execute(
            "SELECT COALESCE(SUM(balance_delta_min), 0) AS tied_sum "
            "FROM session_adjustments WHERE session_id = ? AND adjustment_mode = 'balance_tied'",
            (session_id,),
        ).fetchone()
        tied_sum = float(row["tied_sum"] or 0) if row else 0.0
        return max(0.0, float(duration_min or 0) + tied_sum)

    def _compute_refund_minutes(self, con, session) -> float:
        """Refund capped so payer never receives more than unused prepaid minutes."""
        paid_total = self._session_paid_total(con, session["id"], session["duration_min"])
        elapsed = self._elapsed_minutes_since(session["issued_at"], paid_total)
        prepaid_remaining = max(0.0, paid_total - elapsed)
        remaining_clock = self._minutes_remaining_clock(session["expiry_at"])
        return max(0.0, min(remaining_clock, prepaid_remaining))

    def _append_play_time_event(
        self,
        con,
        player_id: int,
        minutes: float,
        source: str,
        session_id: Optional[int] = None,
        group_id: Optional[int] = None,
        company_id: Optional[int] = None,
        notes: str = "",
        earned_at: Optional[str] = None,
    ):
        con.execute(
            "INSERT INTO play_time_events "
            "(player_id, session_id, group_id, company_id, minutes, source, earned_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                player_id,
                session_id,
                group_id,
                company_id,
                minutes,
                source,
                earned_at or self._now_iso(),
                notes or "",
            ),
        )

    def _credit_day_one_roster_joins(
        self,
        con,
        session_id: int,
        payer_id: int,
        member_ids: list,
        duration_min: float,
        issued_at: str,
        group_id: Optional[int],
        company_id: Optional[int],
    ):
        """Stats-only roster_join for members present at visit start (not the payer)."""
        if duration_min is None:
            return
        minutes = float(duration_min)
        if minutes <= 0:
            return
        for pid in member_ids:
            if pid == payer_id:
                continue
            already = con.execute(
                "SELECT 1 FROM play_time_events WHERE session_id = ? AND player_id = ? "
                "AND source = 'roster_join' LIMIT 1",
                (session_id, pid),
            ).fetchone()
            if already:
                continue
            self._append_play_time_event(
                con,
                pid,
                minutes,
                "roster_join",
                session_id=session_id,
                group_id=group_id,
                company_id=company_id,
                earned_at=issued_at,
            )

    @staticmethod
    def _backfill_day_one_roster_join_ledger(con) -> int:
        """Idempotent: roster_join for historical day-one members missing ledger rows."""
        before = con.execute("SELECT COUNT(*) AS c FROM play_time_events").fetchone()["c"]
        con.execute(
            "INSERT INTO play_time_events "
            "(player_id, session_id, group_id, company_id, minutes, source, earned_at, notes) "
            "SELECT sr.player_id, ps.id, ps.group_id, ps.company_id, CAST(ps.duration_min AS REAL), "
            "'roster_join', ps.issued_at, 'backfill:day_one_roster' "
            "FROM session_roster sr "
            "JOIN player_sessions ps ON ps.id = sr.session_id "
            "WHERE sr.player_id != ps.player_id "
            "AND ps.duration_min IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM play_time_events pte "
            "  WHERE pte.session_id = sr.session_id AND pte.player_id = sr.player_id "
            "  AND pte.source = 'roster_join'"
            ")"
        )
        after = con.execute("SELECT COUNT(*) AS c FROM play_time_events").fetchone()["c"]
        return int(after) - int(before)

    def append_play_time_event(
        self,
        player_id: int,
        minutes: float,
        source: str,
        session_id: Optional[int] = None,
        group_id: Optional[int] = None,
        company_id: Optional[int] = None,
        notes: str = "",
    ):
        with self._lock:
            con = self._conn()
            try:
                self._append_play_time_event(
                    con, player_id, minutes, source, session_id, group_id, company_id, notes
                )
                con.commit()
            finally:
                con.close()

    def _group_has_open_visit(self, con, group_id: int) -> bool:
        row = con.execute(
            "SELECT 1 FROM player_sessions WHERE group_id = ? AND closed_at IS NULL "
            "LIMIT 1",
            (group_id,),
        ).fetchone()
        return row is not None

    def create_session(self, player_id: int, card_id: str, duration_min: int, notes: str = ""):
        now = self._now_iso()
        from datetime import timedelta
        expiry = (datetime.now() + timedelta(minutes=duration_min)).strftime("%Y-%m-%d %H:%M:%S")
        sid = self._executemany_return_id(
            "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
            "duration_min, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (player_id, card_id or "", now, expiry, duration_min, notes),
        )
        return sid, now, expiry

    def issue_session_atomic(self, player_id: int, card_id: str, duration_min: int,
                             notes: str = ""):
        """Create session + seed roster + deduct credit under one lock/transaction.

        Raises ValueError with a staff-facing message on conflict / insufficient credit.
        Returns (session_id, issued_at, expiry_at, credit_balance_after).
        """
        from datetime import timedelta

        with self._lock:
            con = self._conn()
            try:
                now = self._now_iso()
                # Already on any open roster?
                busy = con.execute(
                    "SELECT ps.id, ci.name AS player_name "
                    "FROM session_roster sr "
                    "JOIN player_sessions ps ON ps.id = sr.session_id "
                    "JOIN custom_info ci ON ci.custom_id = ps.player_id "
                    "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                    "ORDER BY ps.expiry_at DESC LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if busy:
                    raise ValueError(
                        f"Player is already on an active team/session "
                        f"(session #{busy['id']}, holder {busy['player_name']}). "
                        f"Remove them from that roster or close that session first."
                    )
                own = con.execute(
                    "SELECT id FROM player_sessions WHERE player_id = ? "
                    "AND closed_at IS NULL AND expiry_at > ? "
                    "ORDER BY expiry_at DESC LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if own:
                    raise ValueError(
                        f"Player already has an open session #{own['id']}. Close it first."
                    )

                grp = con.execute(
                    "SELECT gm.group_id, g.name AS group_name FROM group_members gm "
                    "JOIN groups g ON g.id = gm.group_id "
                    "WHERE gm.player_id = ? AND COALESCE(g.kind, 'team') != 'solo' "
                    "AND g.archived_at IS NULL LIMIT 1",
                    (player_id,),
                ).fetchone()
                if grp:
                    raise ValueError(
                        f"Player is on team '{grp['group_name']}' — use Start Visit for "
                        f"that group, or remove them from the team to allow solo issue."
                    )

                company_membership = con.execute(
                    "SELECT company_id FROM company_members WHERE player_id = ?",
                    (player_id,),
                ).fetchone()
                stamp_company_id = (
                    company_membership["company_id"] if company_membership else None
                )

                bal_row = con.execute(
                    "SELECT credit_balance FROM custom_info WHERE custom_id = ?",
                    (player_id,),
                ).fetchone()
                if not bal_row:
                    raise ValueError("Player not found")
                balance = float(bal_row["credit_balance"] or 0)
                if balance < duration_min:
                    raise ValueError(
                        f"Insufficient credit balance: has {balance:.0f} min, "
                        f"needs {duration_min} min. Top up first."
                    )

                expiry = (datetime.now() + timedelta(minutes=duration_min)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                cur = con.execute(
                    "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
                    "duration_min, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (player_id, card_id or "", now, expiry, duration_min, notes),
                )
                sid = cur.lastrowid
                con.execute(
                    "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) - ? "
                    "WHERE custom_id = ?",
                    (duration_min, player_id),
                )
                con.execute(
                    "INSERT OR IGNORE INTO session_roster (session_id, player_id) VALUES (?, ?)",
                    (sid, player_id),
                )
                if stamp_company_id is not None:
                    con.execute(
                        "UPDATE player_sessions SET company_id = ? WHERE id = ?",
                        (stamp_company_id, sid),
                    )
                self._append_play_time_event(
                    con,
                    player_id,
                    float(duration_min),
                    "visit_start",
                    session_id=sid,
                    group_id=None,
                    company_id=stamp_company_id,
                )
                con.commit()
                return sid, now, expiry, balance - duration_min
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def issue_group_visit_atomic(self, group_id: int, duration_min: int,
                                  card_id: Optional[str] = None, notes: str = ""):
        """Start-visit preflight (all-or-nothing) + issue, single lock/transaction.

        Validates every member before writing anything: same company as the
        group (skipped for walk-in groups), no conflicting open roster/session,
        and (leader only) credit balance + card-binding conflict. Collects ALL
        failures and raises once — nothing is written if any member fails.
        Only on success: bind leader's card (if given), create session, deduct
        leader credit, seed roster, stamp company_id/group_id.

        Returns dict: session_id, player_id (leader), card_id, issued_at,
        expiry_at, duration_min, credit_balance_after.
        """
        from datetime import timedelta

        with self._lock:
            con = self._conn()
            try:
                group = con.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
                if not group:
                    raise ValueError("Group not found")
                if group["archived_at"]:
                    raise ValueError("Group is archived; unarchive it first.")
                leader_id = group["leader_player_id"]
                if not leader_id:
                    raise ValueError("Set a team leader before starting a visit")

                members = con.execute(
                    "SELECT player_id FROM group_members WHERE group_id = ?", (group_id,)
                ).fetchall()
                if not members:
                    raise ValueError("Group has no members")
                member_ids = [m["player_id"] for m in members]

                now = self._now_iso()
                failures = []

                for pid in member_ids:
                    if group["company_id"] is not None:
                        membership = con.execute(
                            "SELECT company_id FROM company_members WHERE player_id = ?",
                            (pid,),
                        ).fetchone()
                        if membership and membership["company_id"] != group["company_id"]:
                            failures.append(
                                f"Player #{pid} belongs to a different company "
                                f"(#{membership['company_id']}); not eligible for this visit."
                            )
                    busy = con.execute(
                        "SELECT ps.id FROM session_roster sr "
                        "JOIN player_sessions ps ON ps.id = sr.session_id "
                        "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ?",
                        (pid, now),
                    ).fetchone()
                    if busy:
                        failures.append(
                            f"Player #{pid} is already on an active team/session "
                            f"(#{busy['id']})."
                        )
                    own = con.execute(
                        "SELECT id FROM player_sessions WHERE player_id = ? "
                        "AND closed_at IS NULL AND expiry_at > ?",
                        (pid, now),
                    ).fetchone()
                    if own:
                        failures.append(f"Player #{pid} already has an open session (#{own['id']}).")

                leader_bal_row = con.execute(
                    "SELECT credit_balance, card_id FROM custom_info WHERE custom_id = ?",
                    (leader_id,),
                ).fetchone()
                if not leader_bal_row:
                    failures.append("Leader player not found")
                    leader_balance = 0.0
                else:
                    leader_balance = float(leader_bal_row["credit_balance"] or 0)
                    if leader_balance < duration_min:
                        failures.append(
                            f"Leader has insufficient credit balance: "
                            f"{leader_balance:.0f} min, needs {duration_min} min."
                        )
                    if card_id and len(card_id) <= 5:
                        failures.append("Card ID invalid (must be > 5 chars)")
                    elif card_id:
                        card_conflict = con.execute(
                            "SELECT custom_id FROM custom_info WHERE card_id = ?",
                            (card_id,),
                        ).fetchone()
                        if card_conflict and card_conflict["custom_id"] != leader_id:
                            failures.append("Card already bound to another player")

                bound_card = ""
                if leader_bal_row:
                    bound_card = (leader_bal_row["card_id"] or "").strip()
                effective_card = (card_id or "").strip() if card_id else bound_card
                if not effective_card or len(effective_card) <= 5:
                    failures.append(
                        "Leader has no RFID card bound; bind a card or pass card_id."
                    )

                if failures:
                    raise ValueError("; ".join(failures))

                if card_id and leader_bal_row["card_id"] != card_id:
                    old_card = leader_bal_row["card_id"] or ""
                    con.execute(
                        "UPDATE custom_info SET card_id = ? WHERE custom_id = ?",
                        (card_id, leader_id),
                    )
                    leader_phone = con.execute(
                        "SELECT phone_num FROM custom_info WHERE custom_id = ?", (leader_id,)
                    ).fetchone()["phone_num"]
                    if old_card:
                        con.execute(
                            "INSERT INTO bind_card_record (custom_phone, action, card_id, date) "
                            "VALUES (?, '0', ?, ?)", (leader_phone, old_card, now),
                        )
                    con.execute(
                        "INSERT INTO bind_card_record (custom_phone, action, card_id, date) "
                        "VALUES (?, '1', ?, ?)", (leader_phone, card_id, now),
                    )
                effective_card = card_id or leader_bal_row["card_id"] or ""

                expiry = (datetime.now() + timedelta(minutes=duration_min)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                cur = con.execute(
                    "INSERT INTO player_sessions (player_id, card_id, issued_at, expiry_at, "
                    "duration_min, notes, company_id, group_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (leader_id, effective_card, now, expiry, duration_min, notes,
                     group["company_id"], group_id),
                )
                sid = cur.lastrowid
                con.execute(
                    "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) - ? "
                    "WHERE custom_id = ?",
                    (duration_min, leader_id),
                )
                for pid in member_ids:
                    con.execute(
                        "INSERT OR IGNORE INTO session_roster (session_id, player_id) VALUES (?, ?)",
                        (sid, pid),
                    )
                self._append_play_time_event(
                    con,
                    leader_id,
                    float(duration_min),
                    "visit_start",
                    session_id=sid,
                    group_id=group_id,
                    company_id=group["company_id"],
                    earned_at=now,
                )
                self._credit_day_one_roster_joins(
                    con,
                    sid,
                    leader_id,
                    member_ids,
                    duration_min,
                    now,
                    group_id,
                    group["company_id"],
                )
                con.commit()
                return {
                    "session_id": sid,
                    "player_id": leader_id,
                    "card_id": effective_card or None,
                    "issued_at": now,
                    "expiry_at": expiry,
                    "duration_min": duration_min,
                    "credit_balance_after": leader_balance - duration_min,
                    "company_id": group["company_id"],
                    "group_id": group_id,
                    "group_name": group["name"],
                }
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def add_roster_member_atomic(self, session_id: int, player_id: int):
        """Add roster member with concurrency checks under one lock/transaction.

        Raises ValueError with a staff-facing message on conflict.
        """
        with self._lock:
            con = self._conn()
            try:
                session = con.execute(
                    "SELECT * FROM player_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not session:
                    raise ValueError("Session not found")
                if session["closed_at"]:
                    raise ValueError("Session already closed")
                now = self._now_iso()
                if (session["expiry_at"] or "") <= now:
                    raise ValueError("Session expired")

                if session["group_id"]:
                    grp = con.execute(
                        "SELECT archived_at FROM groups WHERE id = ?",
                        (session["group_id"],),
                    ).fetchone()
                    if grp and grp["archived_at"]:
                        raise ValueError("Group is archived; unarchive it first.")

                player = con.execute(
                    "SELECT custom_id FROM custom_info WHERE custom_id = ?",
                    (player_id,),
                ).fetchone()
                if not player:
                    raise ValueError("Player not found")

                other = con.execute(
                    "SELECT ps.id, ci.name AS player_name "
                    "FROM session_roster sr "
                    "JOIN player_sessions ps ON ps.id = sr.session_id "
                    "JOIN custom_info ci ON ci.custom_id = ps.player_id "
                    "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                    "ORDER BY ps.expiry_at DESC LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if other and other["id"] != session_id:
                    raise ValueError(
                        f"Player is already on another active team/session "
                        f"(session #{other['id']}, holder {other['player_name']})."
                    )
                own = con.execute(
                    "SELECT id FROM player_sessions WHERE player_id = ? "
                    "AND closed_at IS NULL AND expiry_at > ? "
                    "ORDER BY expiry_at DESC LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if own and own["id"] != session_id:
                    raise ValueError(
                        f"Player already has an open solo/payer session #{own['id']}. "
                        f"Close it before adding them to a team."
                    )

                cur = con.execute(
                    "INSERT OR IGNORE INTO session_roster (session_id, player_id) VALUES (?, ?)",
                    (session_id, player_id),
                )
                if cur.rowcount > 0:
                    already_credited = con.execute(
                        "SELECT 1 FROM play_time_events WHERE session_id = ? AND player_id = ? "
                        "AND source = 'roster_join' LIMIT 1",
                        (session_id, player_id),
                    ).fetchone()
                    if not already_credited:
                        remaining = self._minutes_remaining_clock(session["expiry_at"])
                        if remaining > 0:
                            self._append_play_time_event(
                                con,
                                player_id,
                                remaining,
                                "roster_join",
                                session_id=session_id,
                                group_id=session["group_id"],
                                company_id=session["company_id"],
                            )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def get_active_sessions(self):
        now = self._now_iso()
        rows = self._execute(
            "SELECT ps.*, ci.name AS player_name, ci.phone_num AS phone "
            "FROM player_sessions ps "
            "JOIN custom_info ci ON ci.custom_id = ps.player_id "
            "WHERE ps.closed_at IS NULL AND ps.expiry_at > ? "
            "ORDER BY ps.expiry_at",
            (now,),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def get_session(self, session_id: int):
        return self._row_to_dict(
            self._execute("SELECT * FROM player_sessions WHERE id = ?", (session_id,), fetch="one")
        )

    def get_active_session_by_card(self, card_id: str):
        now = self._now_iso()
        return self._row_to_dict(
            self._execute(
                "SELECT ps.*, ci.name AS player_name "
                "FROM player_sessions ps "
                "JOIN custom_info ci ON ci.custom_id = ps.player_id "
                "WHERE ps.card_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                "ORDER BY ps.expiry_at DESC LIMIT 1",
                (card_id, now),
                fetch="one",
            )
        )

    def get_active_session_by_player(self, player_id: int):
        now = self._now_iso()
        return self._row_to_dict(
            self._execute(
                "SELECT * FROM player_sessions WHERE player_id = ? "
                "AND closed_at IS NULL AND expiry_at > ? "
                "ORDER BY expiry_at DESC LIMIT 1",
                (player_id, now),
                fetch="one",
            )
        )

    def adjust_session(
        self,
        session_id: int,
        delta_min: int,
        reason: str,
        adjusted_by: str = "",
        adjustment_mode: str = "free_clock",
        balance_delta_min: Optional[float] = None,
    ):
        from datetime import timedelta

        mode = adjustment_mode if adjustment_mode in ("free_clock", "balance_tied") else "free_clock"
        bal_delta = float(balance_delta_min if balance_delta_min is not None else delta_min)

        with self._lock:
            con = self._conn()
            try:
                session = con.execute(
                    "SELECT * FROM player_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not session:
                    return None
                if session["closed_at"]:
                    raise ValueError("Session already closed")

                expiry = datetime.strptime(session["expiry_at"], "%Y-%m-%d %H:%M:%S")
                new_expiry = expiry + timedelta(minutes=delta_min)
                new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
                if new_expiry <= datetime.now():
                    raise ValueError(
                        "Adjustment would end the visit now or in the past; close the session instead."
                    )
                payer_id = session["player_id"]

                if mode == "balance_tied" and bal_delta != 0:
                    bal_row = con.execute(
                        "SELECT credit_balance FROM custom_info WHERE custom_id = ?",
                        (payer_id,),
                    ).fetchone()
                    balance = float(bal_row["credit_balance"] or 0) if bal_row else 0.0
                    if bal_delta > 0 and balance < bal_delta:
                        raise ValueError(
                            f"Insufficient credit balance for this adjustment: has {balance:.1f} min, "
                            f"needs {bal_delta:.1f} min. Top up the payer first."
                        )
                    con.execute(
                        "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) - ? "
                        "WHERE custom_id = ?",
                        (bal_delta, payer_id),
                    )
                    self._append_play_time_event(
                        con,
                        payer_id,
                        bal_delta,
                        "adjust",
                        session_id=session_id,
                        group_id=session["group_id"],
                        company_id=session["company_id"],
                        notes=reason or "",
                    )

                con.execute(
                    "UPDATE player_sessions SET expiry_at = ? WHERE id = ?",
                    (new_expiry_str, session_id),
                )
                con.execute(
                    "INSERT INTO session_adjustments "
                    "(session_id, delta_min, reason, adjusted_at, adjusted_by, "
                    "adjustment_mode, balance_delta_min) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        delta_min,
                        reason,
                        self._now_iso(),
                        adjusted_by,
                        mode,
                        bal_delta if mode == "balance_tied" else 0,
                    ),
                )
                con.commit()
                return new_expiry_str
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def close_session(self, session_id: int):
        """Close visit; refund unused clock minutes to payer only (idempotent)."""
        with self._lock:
            con = self._conn()
            try:
                session = con.execute(
                    "SELECT * FROM player_sessions WHERE id = ?", (session_id,)
                ).fetchone()
                if not session:
                    return {
                        "closed": False,
                        "refunded_minutes": 0.0,
                        "payer_player_id": None,
                        "credit_balance_after": None,
                    }
                payer_id = session["player_id"]
                if session["closed_at"]:
                    bal = con.execute(
                        "SELECT credit_balance FROM custom_info WHERE custom_id = ?",
                        (payer_id,),
                    ).fetchone()
                    balance_after = float(bal["credit_balance"] or 0) if bal else 0.0
                    return {
                        "closed": True,
                        "refunded_minutes": 0.0,
                        "payer_player_id": payer_id,
                        "credit_balance_after": balance_after,
                    }

                refunded = self._compute_refund_minutes(con, session)
                if refunded > 0:
                    con.execute(
                        "UPDATE custom_info SET credit_balance = COALESCE(credit_balance, 0) + ? "
                        "WHERE custom_id = ?",
                        (refunded, payer_id),
                    )
                    self._append_play_time_event(
                        con,
                        payer_id,
                        refunded,
                        "refund",
                        session_id=session_id,
                        group_id=session["group_id"],
                        company_id=session["company_id"],
                    )

                now = self._now_iso()
                con.execute(
                    "UPDATE player_sessions SET closed_at = ? WHERE id = ? AND closed_at IS NULL",
                    (now, session_id),
                )
                bal = con.execute(
                    "SELECT credit_balance FROM custom_info WHERE custom_id = ?",
                    (payer_id,),
                ).fetchone()
                balance_after = float(bal["credit_balance"] or 0) if bal else 0.0
                con.commit()
                return {
                    "closed": True,
                    "refunded_minutes": refunded,
                    "payer_player_id": payer_id,
                    "credit_balance_after": balance_after,
                }
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def get_sessions_for_player(self, player_id: int):
        rows = self._execute(
            "SELECT * FROM player_sessions WHERE player_id = ? ORDER BY issued_at DESC",
            (player_id,),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    # ── Session roster (team members for score attribution) ───────────────

    def add_roster_member(self, session_id: int, player_id: int):
        return self._rowcount(
            "INSERT OR IGNORE INTO session_roster (session_id, player_id) VALUES (?, ?)",
            (session_id, player_id),
        )

    def remove_roster_member(self, session_id: int, player_id: int):
        return self._rowcount(
            "DELETE FROM session_roster WHERE session_id = ? AND player_id = ?",
            (session_id, player_id),
        )

    def get_session_roster(self, session_id: int):
        rows = self._execute(
            "SELECT sr.player_id, ci.name, ci.phone_num AS phone, "
            "CASE WHEN ps.player_id = sr.player_id THEN 1 ELSE 0 END AS is_payer "
            "FROM session_roster sr "
            "JOIN custom_info ci ON ci.custom_id = sr.player_id "
            "JOIN player_sessions ps ON ps.id = sr.session_id "
            "WHERE sr.session_id = ? "
            "ORDER BY is_payer DESC, ci.name",
            (session_id,),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def get_open_roster_session_for_player(self, player_id: int):
        """Return open session where this player appears on the roster (any role)."""
        now = self._now_iso()
        return self._row_to_dict(
            self._execute(
                "SELECT ps.*, ci.name AS player_name "
                "FROM session_roster sr "
                "JOIN player_sessions ps ON ps.id = sr.session_id "
                "JOIN custom_info ci ON ci.custom_id = ps.player_id "
                "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                "ORDER BY ps.expiry_at DESC LIMIT 1",
                (player_id, now),
                fetch="one",
            )
        )

    def get_session_for_card_at(self, card_id: str, played_at: Optional[str]):
        """Session that owned this card at played_at (for late poll / roster snapshot)."""
        if not card_id:
            return None
        if not played_at:
            return None
        # Normalize common ISO 'T' separator
        ts = played_at.replace("T", " ")[:19]
        return self._row_to_dict(
            self._execute(
                "SELECT ps.*, ci.name AS player_name "
                "FROM player_sessions ps "
                "JOIN custom_info ci ON ci.custom_id = ps.player_id "
                "WHERE ps.card_id = ? AND ps.issued_at <= ? "
                "AND (ps.closed_at IS NULL OR ps.closed_at >= ?) "
                "ORDER BY ps.issued_at DESC LIMIT 1",
                (card_id, ts, ts),
                fetch="one",
            )
        )

    def get_group_id_for_player(self, player_id: int) -> Optional[int]:
        """Fallback when player_sessions.group_id is unset.

        Prefer the player's open visit group; else solo group; else first active
        non-archived membership. Validate/poller should use session-stamped group_id.
        """
        now = self._now_iso()
        visit = self._execute(
            "SELECT ps.group_id FROM player_sessions ps "
            "WHERE ps.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
            "AND ps.group_id IS NOT NULL "
            "ORDER BY ps.expiry_at DESC LIMIT 1",
            (player_id, now),
            fetch="one",
        )
        if visit and visit["group_id"] is not None:
            return int(visit["group_id"])
        solo = self.get_solo_group_id(player_id)
        if solo is not None:
            return solo
        row = self._execute(
            "SELECT gm.group_id FROM group_members gm "
            "JOIN groups g ON g.id = gm.group_id "
            "WHERE gm.player_id = ? AND g.archived_at IS NULL "
            "ORDER BY g.id DESC LIMIT 1",
            (player_id,),
            fetch="one",
        )
        return int(row["group_id"]) if row else None

    def upsert_central_team_score(self, score: dict) -> Optional[int]:
        """Insert team total; return row id (existing or new).

        Uses SELECT-by-unique-key after INSERT OR IGNORE because SQLite
        lastrowid is unreliable on ignored conflicts.
        """
        with self._lock:
            con = self._conn()
            try:
                params = (
                    score.get("session_id"),
                    score.get("card_id") or "",
                    score.get("player_slot", 1),
                    score["game"],
                    score.get("level", ""),
                    score.get("end_level", ""),
                    score.get("level_file", ""),
                    score.get("end_level_file", ""),
                    score.get("score", 0),
                    score.get("final_score", 0),
                    score.get("member_count", 1),
                    score.get("members_json", "[]"),
                    score.get("life"),
                    score.get("lives_start"),
                    score.get("result"),
                    score.get("time_used", 0),
                    score.get("levels_cleared", 0),
                    score.get("difficulty", ""),
                    score.get("started_at", ""),
                    score.get("played_at"),
                    self._now_iso(),
                    score.get("company_id"),
                    score.get("group_id"),
                    score.get("play_mode"),
                    score.get("roster_size_at_play"),
                    1 if score.get("two_card_play") else 0,
                    score.get("match_key"),
                    score.get("opponent_group_id"),
                    score.get("opponent_card_id"),
                )
                cur = con.execute(
                    "INSERT OR IGNORE INTO central_team_scores "
                    "(session_id, card_id, player_slot, game, level, end_level, "
                    "level_file, end_level_file, "
                    "score, final_score, member_count, members_json, life, lives_start, "
                    "result, time_used, levels_cleared, difficulty, started_at, "
                    "played_at, polled_at, company_id, group_id, play_mode, "
                    "roster_size_at_play, two_card_play, match_key, opponent_group_id, "
                    "opponent_card_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                    "?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    params,
                )
                con.commit()
                if cur.rowcount and cur.lastrowid:
                    return cur.lastrowid
                row = con.execute(
                    "SELECT id FROM central_team_scores WHERE game=? AND card_id=? "
                    "AND player_slot=? AND level=? AND played_at=? AND score=?",
                    (
                        score["game"],
                        score.get("card_id") or "",
                        score.get("player_slot", 1),
                        score.get("level", ""),
                        score.get("played_at"),
                        score.get("score", 0),
                    ),
                ).fetchone()
                return row["id"] if row else None
            finally:
                con.close()

    def upsert_central_score(self, score: dict):
        self._execute(
            "INSERT OR IGNORE INTO central_scores "
            "(player_id, card_id, player_slot, session_id, team_score_id, game, level, end_level, "
            "level_file, end_level_file, "
            "score, final_score, life, lives_start, result, time_used, "
            "levels_cleared, difficulty, started_at, played_at, polled_at, company_id, group_id, "
            "play_mode, roster_size_at_play, two_card_play, match_key, opponent_group_id, "
            "opponent_card_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?)",
            (
                score.get("player_id"),
                score.get("card_id") or "",
                score.get("player_slot", 1),
                score.get("session_id"),
                score.get("team_score_id"),
                score["game"],
                score.get("level", ""),
                score.get("end_level", ""),
                score.get("level_file", ""),
                score.get("end_level_file", ""),
                score.get("score", 0),
                score.get("final_score", 0),
                score.get("life"),
                score.get("lives_start"),
                score.get("result"),
                score.get("time_used", 0),
                score.get("levels_cleared", 0),
                score.get("difficulty", ""),
                score.get("started_at", ""),
                score.get("played_at"),
                self._now_iso(),
                score.get("company_id"),
                score.get("group_id"),
                score.get("play_mode"),
                score.get("roster_size_at_play"),
                1 if score.get("two_card_play") else 0,
                score.get("match_key"),
                score.get("opponent_group_id"),
                score.get("opponent_card_id"),
            ),
        )

    # ── Settings (Task 3.1/3.2: money/time ratios, per-game pushed defaults) ─

    def get_all_settings(self) -> dict:
        rows = self._execute("SELECT key, value FROM settings", fetch="all")
        return {r["key"]: r["value"] for r in rows} if rows else {}

    def set_setting(self, key: str, value: str):
        self._execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def push_game_settings(self, game: str, default_difficulty: str, session_minutes: int):
        self._execute(
            "INSERT INTO game_settings_pushed (game, default_difficulty, session_minutes, pushed_at) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(game) DO UPDATE SET "
            "default_difficulty=excluded.default_difficulty, "
            "session_minutes=excluded.session_minutes, pushed_at=excluded.pushed_at",
            (game, default_difficulty, session_minutes, self._now_iso()),
        )

    def get_pushed_game_settings(self, game: str):
        return self._row_to_dict(
            self._execute(
                "SELECT * FROM game_settings_pushed WHERE game = ?", (game,), fetch="one"
            )
        )

    # ── Poll cursor persistence (Task 3.4) ────────────────────────────────

    def get_poll_cursor(self, game: str):
        row = self._execute(
            "SELECT last_ts FROM poll_cursors WHERE game = ?",
            (game,), fetch="one"
        )
        return row["last_ts"] if row else None

    def set_poll_cursor(self, game: str, last_ts: str):
        self._execute(
            "INSERT INTO poll_cursors (game, last_ts) VALUES (?, ?) "
            "ON CONFLICT(game) DO UPDATE SET last_ts = excluded.last_ts",
            (game, last_ts),
        )

    def update_game_health(self, game: str, status: str, active_game_id: str = ""):
        self._execute(
            "UPDATE game_health SET status=?, last_checked=?, active_game_id=? WHERE game=?",
            (status, self._now_iso(), active_game_id or "", game),
        )

    def get_game_health_all(self):
        rows = self._execute("SELECT * FROM game_health ORDER BY game", fetch="all")
        return [dict(r) for r in rows] if rows else []

    def get_leaderboard(self, game: str = "all", period: str = "alltime", limit: int = 20,
                        company_id: Optional[int] = None, group_id: Optional[int] = None,
                        play_mode: Optional[str] = None, min_size: Optional[int] = None,
                        max_size: Optional[int] = None, two_card: Optional[bool] = None,
                        include_archived: bool = False):
        from .leaderboard import tournament_leaderboard
        return tournament_leaderboard(
            self, board="individual", use_active=False, game=game, period=period,
            limit=limit, company_id=company_id, group_id=group_id, play_mode=play_mode,
            min_size=min_size, max_size=max_size, two_card=two_card,
            include_archived=include_archived,
        )

    def get_team_leaderboard(self, game: str = "all", period: str = "alltime", limit: int = 20,
                             company_id: Optional[int] = None, group_id: Optional[int] = None,
                             play_mode: Optional[str] = None, min_size: Optional[int] = None,
                             max_size: Optional[int] = None, two_card: Optional[bool] = None,
                             include_archived: bool = False):
        from .leaderboard import tournament_leaderboard
        return tournament_leaderboard(
            self, board="team", use_active=False, game=game, period=period, limit=limit,
            company_id=company_id, group_id=group_id, play_mode=play_mode,
            min_size=min_size, max_size=max_size, two_card=two_card,
            include_archived=include_archived,
        )

    # ── Companies / groups (Phase B) ──────────────────────────────────────

    def list_companies(self):
        rows = self._execute(
            "SELECT c.*, "
            "(SELECT COUNT(*) FROM groups g WHERE g.company_id = c.id) AS group_count "
            "FROM companies c ORDER BY c.name",
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def create_company(self, name: str, notes: str = ""):
        cid = self._executemany_return_id(
            "INSERT INTO companies (name, notes, created_at) VALUES (?, ?, ?)",
            (name.strip(), notes or "", self._now_iso()),
        )
        return self.get_company(cid)

    def get_company(self, company_id: int):
        return self._row_to_dict(
            self._execute("SELECT * FROM companies WHERE id = ?", (company_id,), fetch="one")
        )

    def get_company_by_name(self, name: str):
        return self._row_to_dict(
            self._execute(
                "SELECT * FROM companies WHERE lower(name) = lower(?)",
                (name.strip(),),
                fetch="one",
            )
        )

    def update_company(self, company_id: int, name: Optional[str] = None, notes: Optional[str] = None):
        row = self.get_company(company_id)
        if not row:
            return None
        self._execute(
            "UPDATE companies SET name = ?, notes = ? WHERE id = ?",
            (name if name is not None else row["name"],
             notes if notes is not None else (row.get("notes") or ""),
             company_id),
        )
        return self.get_company(company_id)

    def delete_company(self, company_id: int):
        now = self._now_iso()
        open_session = self._execute(
            "SELECT 1 FROM player_sessions WHERE company_id = ? AND closed_at IS NULL "
            "AND expiry_at > ? LIMIT 1", (company_id, now), fetch="one"
        )
        if open_session:
            raise ValueError(
                "Cannot delete company with an active visit; close the session first."
            )
        groups = self.list_groups(company_id)
        for g in groups:
            self._execute("DELETE FROM group_members WHERE group_id = ?", (g["id"],))
        self._execute("DELETE FROM groups WHERE company_id = ?", (company_id,))
        self._execute("DELETE FROM company_members WHERE company_id = ?", (company_id,))
        return self._rowcount("DELETE FROM companies WHERE id = ?", (company_id,))

    # ── Company membership (durable, independent of groups) ────────────────

    def get_company_membership(self, player_id: int):
        return self._row_to_dict(
            self._execute(
                "SELECT cm.*, co.name AS company_name FROM company_members cm "
                "JOIN companies co ON co.id = cm.company_id WHERE cm.player_id = ?",
                (player_id,), fetch="one",
            )
        )

    def get_company_group_map(self, player_ids: list[int]) -> dict:
        """Batch company+group lookup for reception/search screens.

        primary_group_id prefers solo group; group_name lists all active groups.
        """
        if not player_ids:
            return {}
        placeholders = ",".join("?" * len(player_ids))
        rows = self._execute(
            f"SELECT cm.player_id, cm.company_id, co.name AS company_name "
            f"FROM company_members cm "
            f"JOIN companies co ON co.id = cm.company_id "
            f"WHERE cm.player_id IN ({placeholders})",
            tuple(player_ids), fetch="all",
        )
        if not rows:
            return {}
        out: dict = {}
        for r in rows:
            pid = int(r["player_id"])
            groups = self.list_groups_for_player(pid, include_archived=False)
            names = [g["name"] for g in groups]
            primary = self.get_solo_group_id(pid)
            if primary is None and groups:
                primary = int(groups[0]["id"])
            joined = ", ".join(names) if names else None
            out[pid] = {
                "company_id": r["company_id"],
                "company_name": r["company_name"],
                "group_id": primary,
                "primary_group_id": primary,
                "group_name": joined,
                "group_names": joined,
            }
        return out

    def list_company_members(self, company_id: int):
        rows = self._execute(
            "SELECT cm.player_id, cm.joined_at, ci.name, ci.phone_num AS phone "
            "FROM company_members cm "
            "JOIN custom_info ci ON ci.custom_id = cm.player_id "
            "WHERE cm.company_id = ? ORDER BY ci.name",
            (company_id,), fetch="all",
        )
        if not rows:
            return []
        out = []
        for r in rows:
            d = dict(r)
            pid = int(d["player_id"])
            groups = [
                g for g in self.list_groups_for_player(pid, include_archived=False)
                if g.get("company_id") == company_id or g.get("kind") == "solo"
            ]
            team_groups = [g for g in groups if (g.get("kind") or "team") != "solo"]
            primary = self.get_solo_group_id(pid)
            if team_groups:
                d["group_id"] = team_groups[0]["id"]
                d["group_name"] = ", ".join(g["name"] for g in groups)
            elif primary:
                d["group_id"] = primary
                d["group_name"] = next(
                    (g["name"] for g in groups if g["id"] == primary), None
                )
            else:
                d["group_id"] = None
                d["group_name"] = None
            out.append(d)
        return out

    def add_company_member_atomic(self, company_id: int, player_id: int):
        """Raises ValueError if player already belongs to a DIFFERENT company."""
        with self._lock:
            con = self._conn()
            try:
                existing = con.execute(
                    "SELECT company_id FROM company_members WHERE player_id = ?",
                    (player_id,),
                ).fetchone()
                if existing and existing["company_id"] != company_id:
                    walk_id = self._ensure_walk_in_company_row(con)
                    if int(existing["company_id"]) == walk_id:
                        con.execute(
                            "UPDATE company_members SET company_id = ?, joined_at = ? "
                            "WHERE player_id = ?",
                            (company_id, self._now_iso(), player_id),
                        )
                    else:
                        raise ValueError(
                            f"Player already belongs to company #{existing['company_id']}; "
                            f"cannot also join company #{company_id}."
                        )
                else:
                    con.execute(
                        "INSERT OR IGNORE INTO company_members (company_id, player_id, joined_at) "
                        "VALUES (?, ?, ?)",
                        (company_id, player_id, self._now_iso()),
                    )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def remove_company_member(self, company_id: int, player_id: int):
        """Leave company. If on a group under this company: auto-remove from the
        group first, unless there's an open session/roster entry for them (reject
        outright then — closing a live session's org affiliation mid-play is unsafe)."""
        with self._lock:
            con = self._conn()
            try:
                now = self._now_iso()
                busy = con.execute(
                    "SELECT ps.id FROM session_roster sr "
                    "JOIN player_sessions ps ON ps.id = sr.session_id "
                    "WHERE sr.player_id = ? AND ps.closed_at IS NULL AND ps.expiry_at > ? "
                    "LIMIT 1",
                    (player_id, now),
                ).fetchone()
                if busy:
                    raise ValueError(
                        f"Player has an active session (#{busy['id']}); "
                        f"close it before removing them from the company."
                    )
                con.execute(
                    "DELETE FROM group_members WHERE player_id = ? AND group_id IN "
                    "(SELECT id FROM groups WHERE company_id = ?)",
                    (player_id, company_id),
                )
                con.execute(
                    "DELETE FROM company_members WHERE company_id = ? AND player_id = ?",
                    (company_id, player_id),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def list_groups(self, company_id: Optional[int] = None, walk_in_only: bool = False,
                    include_archived: bool = False):
        base = (
            "SELECT g.*, c.name AS company_name, "
            "(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) AS member_count "
            "FROM groups g LEFT JOIN companies c ON c.id = g.company_id "
        )
        archived = "" if include_archived else " AND g.archived_at IS NULL"
        if walk_in_only:
            rows = self._execute(
                base + f"WHERE g.company_id IS NULL{archived} ORDER BY g.name", fetch="all"
            )
        elif company_id is not None:
            rows = self._execute(
                base + f"WHERE g.company_id = ?{archived} ORDER BY g.name",
                (company_id,),
                fetch="all",
            )
        else:
            where = f"WHERE g.archived_at IS NULL" if not include_archived else ""
            rows = self._execute(
                base + f"{where} ORDER BY c.name, g.name", fetch="all"
            )
        return [dict(r) for r in rows] if rows else []

    def create_group(self, company_id: Optional[int], name: str,
                      leader_player_id: Optional[int] = None, kind: str = "team"):
        gid = self._executemany_return_id(
            "INSERT INTO groups (company_id, name, leader_player_id, created_at, kind) "
            "VALUES (?, ?, ?, ?, ?)",
            (company_id, name.strip(), leader_player_id, self._now_iso(), kind),
        )
        if leader_player_id:
            self.add_group_member_atomic(gid, leader_player_id)
        return self.get_group(gid)

    def get_group(self, group_id: int):
        return self._row_to_dict(
            self._execute(
                "SELECT g.*, c.name AS company_name FROM groups g "
                "LEFT JOIN companies c ON c.id = g.company_id WHERE g.id = ?",
                (group_id,),
                fetch="one",
            )
        )

    def get_group_by_company_name(self, company_id: int, name: str):
        return self._row_to_dict(
            self._execute(
                "SELECT * FROM groups WHERE company_id = ? AND lower(name) = lower(?)",
                (company_id, name.strip()),
                fetch="one",
            )
        )

    def update_group(self, group_id: int, name: Optional[str] = None,
                     leader_player_id: Optional[int] = None):
        row = self.get_group(group_id)
        if not row:
            return None
        new_name = name.strip() if name is not None else row["name"]
        new_leader = leader_player_id if leader_player_id is not None else row.get("leader_player_id")
        if (
            leader_player_id is not None
            and leader_player_id != row.get("leader_player_id")
        ):
            with self._lock:
                con = self._conn()
                try:
                    if self._group_has_open_visit(con, group_id):
                        raise ValueError(
                            "Cannot change group leader while a visit is open; close the visit first."
                        )
                finally:
                    con.close()
        self._execute(
            "UPDATE groups SET name = ?, leader_player_id = ? WHERE id = ?",
            (new_name, new_leader, group_id),
        )
        return self.get_group(group_id)

    @staticmethod
    def _group_has_history_conn(con, group_id: int) -> bool:
        if con.execute(
            "SELECT 1 FROM central_scores WHERE group_id = ? LIMIT 1", (group_id,)
        ).fetchone():
            return True
        if con.execute(
            "SELECT 1 FROM central_team_scores WHERE group_id = ? LIMIT 1", (group_id,)
        ).fetchone():
            return True
        if con.execute(
            "SELECT 1 FROM player_sessions WHERE group_id = ? LIMIT 1", (group_id,)
        ).fetchone():
            return True
        return False

    def _group_has_history(self, group_id: int) -> bool:
        with self._lock:
            con = self._conn()
            try:
                return self._group_has_history_conn(con, group_id)
            finally:
                con.close()

    def _archive_group_locked(self, con, group_id: int, allow_solo: bool = False):
        row = con.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        if not row:
            raise ValueError("Group not found")
        if row["kind"] == "solo" and not allow_solo:
            raise ValueError("Cannot archive a player's solo group")
        now = self._now_iso()
        open_session = con.execute(
            "SELECT 1 FROM player_sessions WHERE group_id = ? AND closed_at IS NULL "
            "AND expiry_at > ? LIMIT 1",
            (group_id, now),
        ).fetchone()
        if open_session:
            raise ValueError(
                "Cannot archive group with an active visit; close the session first."
            )
        con.execute(
            "UPDATE groups SET archived_at = ? WHERE id = ?",
            (now, group_id),
        )

    def archive_group(self, group_id: int):
        row = self.get_group(group_id)
        if not row:
            raise ValueError("Group not found")
        with self._lock:
            con = self._conn()
            try:
                self._archive_group_locked(con, group_id, allow_solo=False)
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()
        return self.get_group(group_id)

    def unarchive_group(self, group_id: int):
        if not self.get_group(group_id):
            raise ValueError("Group not found")
        self._execute(
            "UPDATE groups SET archived_at = NULL WHERE id = ?",
            (group_id,),
        )
        return self.get_group(group_id)

    def delete_group(self, group_id: int):
        """Hard-delete only empty groups with no history; else soft-archive."""
        row = self.get_group(group_id)
        if not row:
            raise ValueError("Group not found")
        if row.get("kind") == "solo":
            raise ValueError("Cannot delete a player's solo group")
        now = self._now_iso()
        open_session = self._execute(
            "SELECT 1 FROM player_sessions WHERE group_id = ? AND closed_at IS NULL "
            "AND expiry_at > ? LIMIT 1", (group_id, now), fetch="one"
        )
        if open_session:
            raise ValueError(
                "Cannot delete group with an active visit; close the session first."
            )
        member_count = self._execute(
            "SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?",
            (group_id,), fetch="one",
        )
        members = int(member_count["c"]) if member_count else 0
        if self._group_has_history(group_id):
            self.archive_group(group_id)
            return {"archived": True}
        if members > 0:
            raise ValueError(
                "Group still has members; remove all members before deleting."
            )
        deleted = self._rowcount("DELETE FROM groups WHERE id = ?", (group_id,))
        return {"archived": False, "deleted": deleted > 0}

    def get_group_members(self, group_id: int):
        rows = self._execute(
            "SELECT gm.player_id, ci.name, ci.phone_num AS phone, "
            "CASE WHEN g.leader_player_id = gm.player_id THEN 1 ELSE 0 END AS is_leader "
            "FROM group_members gm "
            "JOIN custom_info ci ON ci.custom_id = gm.player_id "
            "JOIN groups g ON g.id = gm.group_id "
            "WHERE gm.group_id = ? ORDER BY is_leader DESC, ci.name",
            (group_id,),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def add_group_member(self, group_id: int, player_id: int):
        return self._rowcount(
            "INSERT OR IGNORE INTO group_members (group_id, player_id) VALUES (?, ?)",
            (group_id, player_id),
        )

    def add_group_member_atomic(self, group_id: int, player_id: int):
        """Same-company rules for corporate groups; multi-group membership allowed.
        Walk-in groups (company_id IS NULL) skip company checks."""
        with self._lock:
            con = self._conn()
            try:
                group = con.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
                if not group:
                    raise ValueError("Group not found")
                if group["archived_at"]:
                    raise ValueError("Group is archived; unarchive it first.")
                company_id = group["company_id"]

                if company_id is not None:
                    walk_id = self._ensure_walk_in_company_row(con)
                    membership = con.execute(
                        "SELECT company_id FROM company_members WHERE player_id = ?",
                        (player_id,),
                    ).fetchone()
                    if membership and membership["company_id"] != company_id:
                        if int(membership["company_id"]) == walk_id:
                            con.execute(
                                "UPDATE company_members SET company_id = ?, joined_at = ? "
                                "WHERE player_id = ?",
                                (company_id, self._now_iso(), player_id),
                            )
                        else:
                            raise ValueError(
                                f"Player already belongs to company #{membership['company_id']}; "
                                f"cannot join a group under company #{company_id}."
                            )
                    if not membership:
                        con.execute(
                            "INSERT INTO company_members (company_id, player_id, joined_at) "
                            "VALUES (?, ?, ?)",
                            (company_id, player_id, self._now_iso()),
                        )

                con.execute(
                    "INSERT OR IGNORE INTO group_members (group_id, player_id) VALUES (?, ?)",
                    (group_id, player_id),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def transfer_group_member_atomic(self, new_group_id: int, player_id: int):
        """Move a player to new_group_id in one transaction. Rejects if they're
        the leader of their current group (leadership reassignment is a staff
        decision, not something to silently clear/auto-promote)."""
        with self._lock:
            con = self._conn()
            try:
                new_group = con.execute(
                    "SELECT * FROM groups WHERE id = ?", (new_group_id,)
                ).fetchone()
                if not new_group:
                    raise ValueError("Destination group not found")

                old_row = con.execute(
                    "SELECT gm.group_id, g.name, g.leader_player_id, g.company_id "
                    "FROM group_members gm JOIN groups g ON g.id = gm.group_id "
                    "WHERE gm.player_id = ? AND gm.group_id != ? "
                    "AND COALESCE(g.kind, 'team') != 'solo'",
                    (player_id, new_group_id),
                ).fetchone()

                if old_row:
                    if (old_row["company_id"] is not None
                            and new_group["company_id"] is not None
                            and old_row["company_id"] != new_group["company_id"]):
                        raise ValueError(
                            "Cannot transfer across companies; remove the player from "
                            "their current company first, then add them to the new one."
                        )
                    if old_row["leader_player_id"] == player_id:
                        raise ValueError(
                            f"Player is the leader of '{old_row['name']}'; assign a new "
                            f"leader there before transferring them out."
                        )

                new_company_id = new_group["company_id"]
                if new_company_id is not None:
                    membership = con.execute(
                        "SELECT company_id FROM company_members WHERE player_id = ?",
                        (player_id,),
                    ).fetchone()
                    if membership and membership["company_id"] != new_company_id:
                        raise ValueError(
                            f"Player belongs to company #{membership['company_id']}, "
                            f"not #{new_company_id}."
                        )
                    if not membership:
                        con.execute(
                            "INSERT INTO company_members (company_id, player_id, joined_at) "
                            "VALUES (?, ?, ?)",
                            (new_company_id, player_id, self._now_iso()),
                        )

                if old_row:
                    con.execute(
                        "DELETE FROM group_members WHERE group_id = ? AND player_id = ?",
                        (old_row["group_id"], player_id),
                    )
                con.execute(
                    "INSERT OR IGNORE INTO group_members (group_id, player_id) VALUES (?, ?)",
                    (new_group_id, player_id),
                )
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def remove_group_member(self, group_id: int, player_id: int):
        return self._rowcount(
            "DELETE FROM group_members WHERE group_id = ? AND player_id = ?",
            (group_id, player_id),
        )

    def set_group_leader(self, group_id: int, player_id: int):
        with self._lock:
            con = self._conn()
            try:
                if self._group_has_open_visit(con, group_id):
                    raise ValueError(
                        "Cannot change group leader while a visit is open; close the visit first."
                    )
            finally:
                con.close()
        self.add_group_member_atomic(group_id, player_id)
        self._execute(
            "UPDATE groups SET leader_player_id = ? WHERE id = ?",
            (player_id, group_id),
        )
        return self.get_group(group_id)

    def set_session_org(self, session_id: int, company_id: Optional[int], group_id: Optional[int]):
        self._execute(
            "UPDATE player_sessions SET company_id = ?, group_id = ? WHERE id = ?",
            (company_id, group_id, session_id),
        )

    def get_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        # Count team runs when present; fall back to distinct game+card+played_at
        # so split individual rows do not inflate "games".
        games_today = self._execute(
            "SELECT COUNT(*) AS c FROM ("
            "  SELECT 1 FROM central_team_scores WHERE played_at LIKE ? "
            "  UNION ALL "
            "  SELECT 1 FROM central_scores cs "
            "  WHERE cs.played_at LIKE ? AND cs.team_score_id IS NULL "
            "    AND NOT EXISTS ("
            "      SELECT 1 FROM central_team_scores cts "
            "      WHERE cts.game = cs.game AND cts.card_id = cs.card_id "
            "        AND cts.played_at = cs.played_at"
            "    )"
            ")",
            (f"{today}%", f"{today}%"),
            fetch="one",
        )
        games_month = self._execute(
            "SELECT COUNT(*) AS c FROM ("
            "  SELECT 1 FROM central_team_scores WHERE played_at LIKE ? "
            "  UNION ALL "
            "  SELECT 1 FROM central_scores cs "
            "  WHERE cs.played_at LIKE ? AND cs.team_score_id IS NULL "
            "    AND NOT EXISTS ("
            "      SELECT 1 FROM central_team_scores cts "
            "      WHERE cts.game = cs.game AND cts.card_id = cs.card_id "
            "        AND cts.played_at = cs.played_at"
            "    )"
            ")",
            (f"{month}%", f"{month}%"),
            fetch="one",
        )
        unique_today = self._execute(
            "SELECT COUNT(DISTINCT player_id) AS c FROM central_scores "
            "WHERE played_at LIKE ? AND player_id IS NOT NULL",
            (f"{today}%",),
            fetch="one",
        )
        return {
            "games_today": games_today["c"] if games_today else 0,
            "games_month": games_month["c"] if games_month else 0,
            "unique_players_today": unique_today["c"] if unique_today else 0,
        }

    def get_player_history(self, player_id: int):
        player = self.search_custom_tb_by_id(player_id)
        sessions = self.get_sessions_for_player(player_id)
        scores = self._execute(
            "SELECT * FROM central_scores WHERE player_id = ? ORDER BY played_at DESC",
            (player_id,),
            fetch="all",
        )
        return {
            "player": player[0] if player else None,
            "sessions": sessions,
            "scores": [dict(r) for r in scores] if scores else [],
            "recharge_history": self.search_recharge_tb_by_id(player_id),
        }

    def verify_login(self, username: str, password: str) -> bool:
        rows = self._execute("SELECT name, password FROM ledplay_login LIMIT 1", fetch="one")
        if not rows:
            return True
        return rows["name"] == username and rows["password"] == password

    def change_admin_password(self, username: str, password: str):
        self.delete_table_data("ledplay_login")
        self.insert_to_table_login(username, password)


_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
