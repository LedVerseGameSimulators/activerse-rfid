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
                        company_id        INTEGER NOT NULL,
                        name              TEXT NOT NULL,
                        leader_player_id  INTEGER,
                        created_at        TEXT,
                        UNIQUE(company_id, name)
                    );

                    CREATE TABLE IF NOT EXISTS group_members (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        group_id   INTEGER NOT NULL,
                        player_id  INTEGER NOT NULL,
                        UNIQUE(group_id, player_id)
                    );
                """)
                # Idempotent ALTERs for central_scores (existing DBs upgrading
                # from the pre-per-player schema).
                for _col, _typ in (("player_slot", "INTEGER"), ("end_level", "TEXT"),
                                   ("final_score", "REAL"), ("lives_start", "INTEGER"),
                                   ("levels_cleared", "INTEGER"), ("difficulty", "TEXT"),
                                   ("started_at", "TEXT"), ("team_score_id", "INTEGER"),
                                   ("company_id", "INTEGER")):
                    try:
                        con.execute(f"ALTER TABLE central_scores ADD COLUMN {_col} {_typ}")
                    except sqlite3.OperationalError:
                        pass
                for _col, _typ in (("company_id", "INTEGER"), ("group_id", "INTEGER")):
                    try:
                        con.execute(f"ALTER TABLE player_sessions ADD COLUMN {_col} {_typ}")
                    except sqlite3.OperationalError:
                        pass
                try:
                    con.execute("ALTER TABLE central_team_scores ADD COLUMN company_id INTEGER")
                except sqlite3.OperationalError:
                    pass
                # Optional columns on custom_info
                for col, typ in (("email", "TEXT"), ("age", "INTEGER"), ("notes", "TEXT"),
                                ("credit_balance", "REAL DEFAULT 0")):
                    try:
                        con.execute(f"ALTER TABLE custom_info ADD COLUMN {col} {typ}")
                    except sqlite3.OperationalError:
                        pass
                # Rebuild central_scores unique key so team split shares
                # (same card/score, different player_id) do not collapse.
                self._migrate_central_scores_unique(con)
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
        self._execute("DELETE FROM custom_info WHERE custom_id = ?", (player_id,))

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
                con.commit()
                return sid, now, expiry, balance - duration_min
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

                con.execute(
                    "INSERT OR IGNORE INTO session_roster (session_id, player_id) VALUES (?, ?)",
                    (session_id, player_id),
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

    def adjust_session(self, session_id: int, delta_min: int, reason: str, adjusted_by: str = ""):
        session = self.get_session(session_id)
        if not session:
            return None
        from datetime import datetime, timedelta
        expiry = datetime.strptime(session["expiry_at"], "%Y-%m-%d %H:%M:%S")
        new_expiry = expiry + timedelta(minutes=delta_min)
        new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        self._execute(
            "UPDATE player_sessions SET expiry_at = ? WHERE id = ?",
            (new_expiry_str, session_id),
        )
        self._execute(
            "INSERT INTO session_adjustments (session_id, delta_min, reason, adjusted_at, adjusted_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, delta_min, reason, self._now_iso(), adjusted_by),
        )
        return new_expiry_str

    def close_session(self, session_id: int):
        return self._rowcount(
            "UPDATE player_sessions SET closed_at = ? WHERE id = ? AND closed_at IS NULL",
            (self._now_iso(), session_id),
        )

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
        if played_at:
            # Normalize common ISO 'T' separator
            ts = played_at.replace("T", " ")[:19]
            row = self._row_to_dict(
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
            if row:
                return row
        return self.get_active_session_by_card(card_id)

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
                )
                cur = con.execute(
                    "INSERT OR IGNORE INTO central_team_scores "
                    "(session_id, card_id, player_slot, game, level, end_level, "
                    "score, final_score, member_count, members_json, life, lives_start, "
                    "result, time_used, levels_cleared, difficulty, started_at, "
                    "played_at, polled_at, company_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            "score, final_score, life, lives_start, result, time_used, "
            "levels_cleared, difficulty, started_at, played_at, polled_at, company_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                score.get("player_id"),
                score.get("card_id") or "",
                score.get("player_slot", 1),
                score.get("session_id"),
                score.get("team_score_id"),
                score["game"],
                score.get("level", ""),
                score.get("end_level", ""),
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
                        company_id: Optional[int] = None):
        clauses = ["1=1"]
        params: list = []
        if game != "all":
            clauses.append("cs.game = ?")
            params.append(game)
        if company_id is not None:
            clauses.append("cs.company_id = ?")
            params.append(company_id)
        now = datetime.now()
        if period == "today":
            clauses.append("cs.played_at >= ?")
            params.append(now.strftime("%Y-%m-%d 00:00:00"))
        elif period == "week":
            from datetime import timedelta
            clauses.append("cs.played_at >= ?")
            params.append((now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        elif period == "month":
            clauses.append("cs.played_at >= ?")
            params.append(now.strftime("%Y-%m-01 00:00:00"))
        where = " AND ".join(clauses)
        params.append(limit)
        rows = self._execute(
            f"SELECT cs.*, ci.name AS player_name FROM central_scores cs "
            f"LEFT JOIN custom_info ci ON ci.custom_id = cs.player_id "
            f"WHERE {where} ORDER BY COALESCE(cs.final_score, cs.score) DESC LIMIT ?",
            tuple(params),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def get_team_leaderboard(self, game: str = "all", period: str = "alltime", limit: int = 20,
                             company_id: Optional[int] = None):
        clauses = ["cts.member_count >= 2"]
        params: list = []
        if game != "all":
            clauses.append("cts.game = ?")
            params.append(game)
        if company_id is not None:
            clauses.append("cts.company_id = ?")
            params.append(company_id)
        now = datetime.now()
        if period == "today":
            clauses.append("cts.played_at >= ?")
            params.append(now.strftime("%Y-%m-%d 00:00:00"))
        elif period == "week":
            from datetime import timedelta
            clauses.append("cts.played_at >= ?")
            params.append((now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S"))
        elif period == "month":
            clauses.append("cts.played_at >= ?")
            params.append(now.strftime("%Y-%m-01 00:00:00"))
        where = " AND ".join(clauses)
        params.append(limit)
        rows = self._execute(
            f"SELECT cts.* FROM central_team_scores cts "
            f"WHERE {where} ORDER BY COALESCE(cts.final_score, cts.score) DESC LIMIT ?",
            tuple(params),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

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
        groups = self.list_groups(company_id)
        for g in groups:
            self._execute("DELETE FROM group_members WHERE group_id = ?", (g["id"],))
        self._execute("DELETE FROM groups WHERE company_id = ?", (company_id,))
        return self._rowcount("DELETE FROM companies WHERE id = ?", (company_id,))

    def list_groups(self, company_id: Optional[int] = None):
        if company_id is not None:
            rows = self._execute(
                "SELECT g.*, c.name AS company_name, "
                "(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) AS member_count "
                "FROM groups g JOIN companies c ON c.id = g.company_id "
                "WHERE g.company_id = ? ORDER BY g.name",
                (company_id,),
                fetch="all",
            )
        else:
            rows = self._execute(
                "SELECT g.*, c.name AS company_name, "
                "(SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = g.id) AS member_count "
                "FROM groups g JOIN companies c ON c.id = g.company_id ORDER BY c.name, g.name",
                fetch="all",
            )
        return [dict(r) for r in rows] if rows else []

    def create_group(self, company_id: int, name: str, leader_player_id: Optional[int] = None):
        gid = self._executemany_return_id(
            "INSERT INTO groups (company_id, name, leader_player_id, created_at) VALUES (?, ?, ?, ?)",
            (company_id, name.strip(), leader_player_id, self._now_iso()),
        )
        if leader_player_id:
            self.add_group_member(gid, leader_player_id)
        return self.get_group(gid)

    def get_group(self, group_id: int):
        return self._row_to_dict(
            self._execute(
                "SELECT g.*, c.name AS company_name FROM groups g "
                "JOIN companies c ON c.id = g.company_id WHERE g.id = ?",
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
        self._execute(
            "UPDATE groups SET name = ?, leader_player_id = ? WHERE id = ?",
            (new_name, new_leader, group_id),
        )
        return self.get_group(group_id)

    def delete_group(self, group_id: int):
        self._execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
        return self._rowcount("DELETE FROM groups WHERE id = ?", (group_id,))

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

    def remove_group_member(self, group_id: int, player_id: int):
        return self._rowcount(
            "DELETE FROM group_members WHERE group_id = ? AND player_id = ?",
            (group_id, player_id),
        )

    def set_group_leader(self, group_id: int, player_id: int):
        self.add_group_member(group_id, player_id)
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
            "SELECT COUNT(DISTINCT COALESCE(player_id, card_id)) AS c FROM central_scores "
            "WHERE played_at LIKE ?",
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
