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

                    CREATE TABLE IF NOT EXISTS central_scores (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        player_id   INTEGER,
                        card_id     TEXT,
                        session_id  INTEGER,
                        game        TEXT,
                        level       TEXT,
                        score       REAL,
                        score2      REAL,
                        life        INTEGER,
                        result      INTEGER,
                        time_used   REAL,
                        played_at   TEXT,
                        polled_at   TEXT,
                        UNIQUE(game, card_id, level, played_at, score)
                    );

                    CREATE TABLE IF NOT EXISTS game_health (
                        game            TEXT PRIMARY KEY,
                        status          TEXT,
                        last_checked    TEXT,
                        active_game_id  TEXT
                    );
                """)
                # Optional columns on custom_info
                for col, typ in (("email", "TEXT"), ("age", "INTEGER"), ("notes", "TEXT")):
                    try:
                        con.execute(f"ALTER TABLE custom_info ADD COLUMN {col} {typ}")
                    except sqlite3.OperationalError:
                        pass
                # Seed default admin if empty
                row = con.execute("SELECT COUNT(*) AS c FROM ledplay_login").fetchone()
                if row["c"] == 0:
                    con.execute(
                        "INSERT INTO ledplay_login (name, password) VALUES (?, ?)",
                        ("admin", os.getenv("ADMIN_PASSWORD", "admin")),
                    )
                # Seed game_health rows
                for game in ("hoops", "climb", "led_hex", "laser"):
                    con.execute(
                        "INSERT OR IGNORE INTO game_health (game, status) VALUES (?, 'down')",
                        (game,),
                    )
                con.commit()
            finally:
                con.close()

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

    def search_from_table(self, table: str):
        rows = self._execute(f"SELECT * FROM {table}", fetch="all")
        return [tuple(dict(r).values()) for r in rows] if rows else []

    def delete_table_data(self, table: str):
        self._execute(f"DELETE FROM {table}")

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

    def upsert_central_score(self, score: dict):
        self._execute(
            "INSERT OR IGNORE INTO central_scores "
            "(player_id, card_id, session_id, game, level, score, score2, life, "
            "result, time_used, played_at, polled_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                score.get("player_id"),
                score.get("card_id") or "",
                score.get("session_id"),
                score["game"],
                score.get("level", ""),
                score.get("score", 0),
                score.get("score2", 0),
                score.get("life"),
                score.get("result"),
                score.get("time_used", 0),
                score.get("played_at"),
                self._now_iso(),
            ),
        )

    def update_game_health(self, game: str, status: str, active_game_id: str = ""):
        self._execute(
            "UPDATE game_health SET status=?, last_checked=?, active_game_id=? WHERE game=?",
            (status, self._now_iso(), active_game_id or "", game),
        )

    def get_game_health_all(self):
        rows = self._execute("SELECT * FROM game_health ORDER BY game", fetch="all")
        return [dict(r) for r in rows] if rows else []

    def get_leaderboard(self, game: str = "all", period: str = "alltime", limit: int = 20):
        clauses = ["1=1"]
        params: list = []
        if game != "all":
            clauses.append("cs.game = ?")
            params.append(game)
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
            f"WHERE {where} ORDER BY cs.score DESC LIMIT ?",
            tuple(params),
            fetch="all",
        )
        return [dict(r) for r in rows] if rows else []

    def get_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")
        games_today = self._execute(
            "SELECT COUNT(*) AS c FROM central_scores WHERE played_at LIKE ?",
            (f"{today}%",),
            fetch="one",
        )
        games_month = self._execute(
            "SELECT COUNT(*) AS c FROM central_scores WHERE played_at LIKE ?",
            (f"{month}%",),
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
