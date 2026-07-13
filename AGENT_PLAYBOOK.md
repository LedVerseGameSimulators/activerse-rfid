# Activerse RFID Server — Agent Playbook

**Repo:** `/Users/apple/activerse_final_changes/activerse-rfid/`  
**Source (original Windows app, fully decompiled):** `/Users/apple/parallel-work/ledplayserver_decompiled/`  
**Original full UI tree:** `/Users/apple/parallel-work/ledplayserver_py_source/ui/`  
**Port:** API `:9000`, React UI `:5174` (Vite)

---

## What this app is

Reception/admin desk for an LED floor game kiosk arcade.  
Staff runs this on one machine. Controls all 4 game machines (hoops, climb, led_hex, laser) over LAN.

**Two operational modes:**
- **Mode 1 (current, already works):** Staff manually registers player → issues session → player plays. No RFID scan at game machine.
- **Mode 2 (to add):** Player taps RFID card at game machine → machine calls `/validate?card_id=XXX` → server returns valid/invalid + time remaining. Player plays without staff intervention.

Both modes use the same database. Mode 2 just adds the physical card scan step.

---

## Requirements (user-confirmed)

1. **Phone = unique identifier.** Name + phone mandatory. Email + age optional.
2. **Session duration:** free-form input, default 60 min. Staff can type any value.
3. **Add/subtract minutes:** from any active session, with reason text.
4. **Two modes** described above.
5. **Admin login** protects the panel (username/password).
6. **Score poller** pulls scores from all 4 game APIs every 120s.
7. **Central leaderboard** across all games, filterable by game + period.
8. **No RFID required to register** — phone number is enough. Card binding is optional, done later.

---

## Current Code State

### Backend — COMPLETE ✓

| File | Status | What it does |
|------|--------|-------------|
| `api/main.py` | Done | All REST endpoints |
| `api/database.py` | Done | SQLite (dev) + MySQL (prod), all tables |
| `api/players.py` | Done | Register, list, get, update, bind/unbind card |
| `api/sessions.py` | Done | Issue, adjust, close, validate |
| `api/dashboard.py` | Done | Health, leaderboard, stats, player history |
| `api/poller.py` | Done | Background async loop every 120s |
| `api/config.py` | Done | Game registry, ports, session rules |
| `api/models.py` | Done | Pydantic schemas |
| `requirements.txt` | Done | fastapi, uvicorn, httpx, loguru, pydantic |

### Frontend — COMPLETE ✓

| Screen | Status | What it does |
|--------|--------|-------------|
| `Login.jsx` | Done | Admin username/password gate |
| `ReceptionDesk.jsx` | Done | New visitor tab (register) + Returning visitor tab (search→card→session) |
| `RegisterPlayer.jsx` | Done | Name, phone, email, age, public checkbox |
| `PlayerSearch.jsx` | Done | Search by name/phone/card |
| `PlayerCard.jsx` | Done | Shows player info + active session + issue/adjust buttons |
| `IssueSession.jsx` | Done | Duration input (free-form int), notes, confirm |
| `AdjustSession.jsx` | Done | delta_min input (negative = subtract), reason text |
| `BindCard.jsx` | Done | Card ID input → bind to player |
| `PlayerAdmin.jsx` | Done | Full player table, search, bind card |
| `Dashboard.jsx` | Done | Game health tiles, stats, leaderboard (filter by game + period) |
| `Settings.jsx` | Done | Change admin password |

### DB Tables (auto-created on first run)

```
custom_info        — players (phone_num UNIQUE, name, card_id, time_left, email, age, notes)
recharge_record    — time top-up history (custom_id, money, game_time, date)
bind_card_record   — card bind/unbind audit trail
ledplay_login      — admin credentials (seeded: admin/admin)
player_sessions    — issued sessions (player_id, card_id, issued_at, expiry_at, duration_min)
session_adjustments — add/subtract log (session_id, delta_min, reason, adjusted_by)
central_scores     — polled scores from all games (game, card_id, level, score, played_at)
game_health        — last-known status per game machine
```

---

## Game Repos — All 5 Games

The RFID server is the central hub. All 5 game machines run independently and the RFID server polls them + validates cards against them.

### Port Map (full system)

| Service | Repo | API Port | WS Port | UI Port | GAME_NAME key |
|---------|------|----------|---------|---------|---------------|
| Hoops | `led-hoops` | 8000 | 8765 | 5173 | `hoops` |
| Laser Trap | `led-laser` | 8001 | 8768 | 5174 | `laser` |
| Climb | `led-climb` | 8002 | 8766 | 5175 | `climb` |
| Floor Is Lava | `led-grid` | 8003 | 8769 | 5176 | `grid` |
| LED Hexagon | `led-hexagon` | 8004 | 8767 | 5177 | `led_hex` |
| **RFID Server** | `activerse-rfid` | **9000** | — | **5178** | — |

All repos live at: `/Users/apple/activerse_final_changes/<repo>/`

---

### Per-Game Details

#### 1. Hoops (`led-hoops`, port 8000)
- **Grid:** 1 row × 6 cols (hoop strip — players shoot hoops at physical hoops)
- **Level series:** `-` (casual), `--`, `---`, `1casual game`, `2level game` (5 folders)
- **Gameplay:** Players shoot basketball through hoops. Each hoop = score zone. Timer-based.
- **Scoring:** Score per hoop made. 1P and 2P variants.
- **Run:** `python3 -m api.main` → :8000 · `python3 ws_bridge.py` → :8765 · `npm run dev` → :5173

#### 2. Laser Trap (`led-laser`, port 8001)
- **Grid:** 6 rows × 16 cols (rectangular floor)
- **Level series:** `-`, `--`, `---`, `----` (4 folders + `测试123.led` test file)
- **Gameplay:** Laser beams cross the floor. Players dodge/navigate without hitting lasers. 1P only — no `.ledb` 2P levels exist for this game.
- **Scoring:** Survival time + completion bonus.
- **Run:** `python3 -m api.main` → :8001 · `python3 ws_bridge.py` → :8768 · `npm run dev` → :5174

#### 3. Climb (`led-climb`, port 8002)
- **Grid:** 6 rows × 33 cols (rectangular floor tiles)
- **Level series:** `-` (A-series, 25 levels), `--` (B-series, 31 levels), `---` (DK-series, 9 2P levels)
- **Gameplay:** Step blue/coloured tiles → +1 score. Red tiles = hazard (-1 life/1.2s). Green = shield. 5-min session, 20 lives persist across levels.
- **Scoring:** Score divided by player count and time. `game_scode_divide_person=True`, `game_scode_divide_time=True`.
- **2P mode:** Blue = P1, Orange = P2. DK-series levels use checkerboard spatial split.
- **Run:** `python3 -m api.main` → :8002 · `python3 ws_bridge.py` → :8766 · `npm run dev` → :5175

#### 4. Floor Is Lava / Grid (`led-grid`, port 8003)
- **Grid:** 16 rows × 26 cols (rectangular floor tiles, single RGB per cell)
- **Level series:** `-` (10 levels), `--` (15 levels), `---` (14 hard), `----` (12 2P `.ledb`, live tier — a separate `---/---/` nested directory also contains `.ledb` files but is dead code, never globbed by the level loader)
- **Gameplay:** Avoid red lava tiles, step blue safe tiles. Green = shield. 5-min session, 20 lives.
- **Scoring:** Raw score = final score. NO division (`game_scode_divide_person=False`, `game_scode_divide_time=False`).
- **Run:** `python3 -m api.main` → :8003 · `python3 ws_bridge.py` → :8769 · `npm run dev` → :5176

#### 5. LED Hexagon (`led-hexagon`, port 8004)
- **Grid:** 16 rows × 26 cols (hexagonal floor with 3-ring RGB per cell — DIFFERENT from other games)
- **Level series:** `-` (pro, 17 levels), `--` (advanced/YC memory-mode, 18 levels), `---` (2P DK + YCDK memory-mode, 22 levels)
- **Gameplay:** Hexagonal LED floor. Multi-ring colour targets. Step tiles to score. `--`/YCDK-tier levels add a memory mechanic: targets reveal for 5s then hide as camouflage teal, with a hint tile (alternates P1/P2 color in 2P) that re-reveals for a -5 score cost.
- **Scoring:** Per-cell score. 3-ring RGB each cell (not single RGB like other games).
- **Special:** Simulator uses hexagonal canvas rendering, not square grid.
- **Run:** `python3 -m api.main` → :8004 · `python3 ws_bridge.py` → :8767 · `npm run dev` → :5177

---

### How to run all 5 games + RFID server together

Each game needs 3 processes (API + WS bridge + React UI). Full system = 16 processes total.

```bash
# Hoops
cd /Users/apple/activerse_final_changes/led-hoops
python3 -m api.main &
python3 ws_bridge.py &
cd frontend && npm run dev &

# Climb
cd /Users/apple/activerse_final_changes/led-climb
python3 -m api.main &
python3 ws_bridge.py &
cd frontend && npm run dev &

# LED Hexagon
cd /Users/apple/activerse_final_changes/led-hexagon
python3 -m api.main &
python3 ws_bridge.py &
cd frontend && npm run dev &

# Laser Trap
cd /Users/apple/activerse_final_changes/led-laser
python3 -m api.main &
python3 ws_bridge.py &
cd frontend && npm run dev &

# Floor Is Lava
cd /Users/apple/activerse_final_changes/led-grid
python3 -m api.main &
python3 ws_bridge.py &
cd frontend && npm run dev &

# RFID Server
cd /Users/apple/activerse_final_changes/activerse-rfid
python3 -m api.main &
cd frontend && npm run dev &
```

A `start-all-games.sh` shell script should be created at `/Users/apple/activerse_final_changes/scripts/` to do this in one command (see pending tasks in Phase 1 section).

---

### What each game exposes to the RFID server

The RFID poller calls these endpoints on each game API:

| Endpoint | Used for |
|----------|---------|
| `GET /health` | Check if game machine is running. Returns `{"status":"ok"}` |
| `GET /scores?since=<iso_timestamp>` | Pull new completed game scores since last poll |

The RFID server also (future): pushes card validation. Each game calls:

| Endpoint | Used for |
|----------|---------|
| `GET http://rfid-server:9000/validate?card_id=XXX` | Check if card has active session/allocation |

**`/scores` response format** (must be consistent across ALL 5 game APIs):
```json
{
  "success": true,
  "scores": [
    {
      "card_id": "2282047570",
      "level": "A005.led",
      "score": 42,
      "score2": 0,
      "life": 15,
      "result": 1,
      "time_used": 4.8,
      "ts": "2026-06-12 14:33:01",
      "game": "climb"
    }
  ]
}
```

`card_id` is the key that links scores back to a player in the RFID server. If `card_id` is empty (game played without RFID scan), score is stored anonymously.

---

### Score DB location per game

Each game stores scores in its own SQLite file. All point to same shared file:

```
/Users/apple/parallel-work/ledhexagon_clone/setting/ledplaydb.sqlite
```

This is the `_SCORES_DB` path in each game's `api/database.py`. All 5 games write to the `hex_scores` table in this shared file. The RFID poller reads from this same file (or via the `/scores` API endpoint — preferred for LAN deployment).

---

## What Still Needs To Be Done

### 1. Add `/scores?since=` to each game API (CRITICAL for poller)

The poller (`api/poller.py`) calls `GET /scores?since=<iso_timestamp>` on each game API.  
This endpoint must exist on all 4 game servers. **led-climb already has it** (`database.py → get_scores_since()`), but it may not be wired into `api/main.py` on each game.

**For each game repo (`led-climb`, `led-hexagon`, `led-hoops`, `led-laser`):**

Check `api/main.py` for a `/scores` endpoint. If missing, add:

```python
@app.get("/scores")
async def scores_since(since: str = Query(default="2000-01-01T00:00:00")):
    db = get_db()
    rows = db.get_scores_since(since)
    return {"success": True, "scores": rows}
```

And in each game's `api/database.py`, `get_scores_since()` must exist:

```python
def get_scores_since(self, since: str):
    with self._scores_lock:
        con = self._scores_conn()
        rows = con.execute(
            "SELECT card_id, level, score, score2, life, result, time_used, ts, game "
            "FROM hex_scores WHERE ts > ? ORDER BY ts ASC",
            (since,),
        ).fetchall()
        con.close()
    return [dict(zip(
        ["card_id","level","score","score2","life","result","time_used","ts","game"], r
    )) for r in rows]
```

### 2. Add `led-grid` (Floor Is Lava) to game registry

In `api/config.py`:

```python
GAME_REGISTRY = {
    "hoops":   {"api": os.getenv("HOOPS_API",   "http://localhost:8000"), "label": "Hoops"},
    "laser":   {"api": os.getenv("LASER_API",   "http://localhost:8001"), "label": "Laser Trap"},
    "climb":   {"api": os.getenv("CLIMB_API",   "http://localhost:8002"), "label": "Climb"},
    "grid":    {"api": os.getenv("GRID_API",    "http://localhost:8003"), "label": "Floor Is Lava"},
    "led_hex": {"api": os.getenv("LED_HEX_API", "http://localhost:8004"), "label": "LED Hex"},
}
```

Also add a seed row in `database.py → _ensure_tables()`:
```python
for game in ("hoops", "climb", "led_hex", "laser", "grid"):  # add "grid"
```

And add to Dashboard.jsx `<select>`:
```jsx
<option value="grid">Floor Is Lava</option>
```

### 3. Edit player screen (minor gap)

`PlayerAdmin.jsx` shows bind-card only. Should also let staff edit name/email/age/notes.  
Add "Edit" button per row → modal with `PUT /players/{id}` call.  
Use existing `PlayerUpdate` Pydantic model (already in `models.py`).

### 4. Delete player (present in original, missing in frontend)

Original had a "注销" (deactivate/delete) button.  
Backend needs `DELETE /players/{player_id}` endpoint → `db.delete_table_row_by_id("custom_info", player_id)`.  
Add to `players.py` and wire in `main.py`. Then add delete button in `PlayerAdmin.jsx`.

### 5. Recharge history view (original: `recharge_record` table)

Original showed staff a table of all top-up events (who, how much time, when).  
Currently no frontend screen for this. Add tab or route `/players/{id}` detail page that shows:
- Session history (already in `get_player` response)
- Recharge history (add `db.search_recharge_tb_by_id(player_id)` — method exists in db_operation.py already)

Wire `search_recharge_tb_by_id` in `database.py`:
```python
def search_recharge_tb_by_id(self, custom_id: int):
    rows = self._execute(
        "SELECT * FROM recharge_record WHERE custom_id = ? ORDER BY date DESC",
        (str(custom_id),), fetch="all"
    )
    return [dict(r) for r in rows] if rows else []
```

### 6. Mode 2 — RFID scan at game machine (if needed)

The `/validate?card_id=XXX` endpoint is **already implemented**. Returns:
```json
{"valid": true, "player_name": "...", "session_id": 123, "minutes_remaining": 45.5}
{"valid": false, "reason": "no_active_session"}
{"valid": false, "reason": "expired"}
```

Each game machine's React frontend needs to:
1. Call `GET http://rfid-server:9000/validate?card_id=<scanned_card>`
2. On `valid=true` → show player name, start game
3. On `valid=false` → show reason, block game start

This is a game-side change, not an RFID server change.

---

## How to Run

### Backend
```bash
cd /Users/apple/activerse_final_changes/activerse-rfid
pip3 install -r requirements.txt
python3 -m api.main
# → http://localhost:9000
# → API docs at http://localhost:9000/docs
```

### Frontend
```bash
cd /Users/apple/activerse_final_changes/activerse-rfid/frontend
npm install
npm run dev
# → http://localhost:5174
```

### First-run defaults
- Admin login: `admin` / `admin` (change in Settings tab)
- DB auto-created at: `data/rfid.sqlite`
- Game APIs: localhost:8000–8003 (override via `.env`)

### .env (optional, create in repo root)
```env
ADMIN_PASSWORD=yourpassword
DB_PATH=data/rfid.sqlite
HOOPS_API=http://192.168.1.101:8000
LASER_API=http://192.168.1.102:8001
CLIMB_API=http://192.168.1.103:8002
GRID_API=http://192.168.1.104:8003
LED_HEX_API=http://192.168.1.105:8004
POLL_INTERVAL_SECONDS=120
DEFAULT_SESSION_MINUTES=60
MIN_MINUTES_TO_START=5
API_PORT=9000
```

---

## Testing Steps (in order)

1. **Backend starts without error:** `python3 -m api.main` → no crash
2. **Swagger UI loads:** `http://localhost:9000/docs`
3. **Health endpoint:** `GET /health` → `{"status":"ok"}`
4. **Login:** `POST /auth/login` `{"username":"admin","password":"admin"}` → `{"success":true}`
5. **Register player:** `POST /players` `{"name":"Test","phone":"0401234567"}` → player object with `id`
6. **Issue session:** `POST /sessions` `{"player_id":1,"duration_min":60}` → session with `expiry_at`
7. **Validate card:** bind card first via `POST /players/1/bind-card {"card_id":"TESTCARD123"}`, then `GET /validate?card_id=TESTCARD123` → `{"valid":true,...}`
8. **Adjust session:** `POST /sessions/1/adjust` `{"delta_min":-10,"reason":"test"}` → new expiry 10 min earlier
9. **Frontend loads:** `http://localhost:5174` → login screen
10. **Registration flow:** Login → Reception → New Visitor → fill form → Register → success
11. **Session flow:** Reception → Returning Visitor → search by phone → Issue Session → 60 min → Confirm
12. **Dashboard:** Dashboard tab shows 4 game health tiles (all "down" until game APIs run)
13. **Poller test:** `POST /internal/poll-now` → `{"success":true}` (games show "down", not crash)

---

## Source Reference (decompiled original)

All original logic is readable at:

| File | What to reference |
|------|------------------|
| `/Users/apple/parallel-work/ledplayserver_decompiled/db_operation.py` | All original SQL queries |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/ui_customer_regist.py` | Register flow |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/ui_recharge.py` | Add time flow (time_left += game_time) |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/ui_bindcard.py` | Card bind/unbind logic |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/ui_main.py` | Main table/search/delete flow |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/login.py` | Login flow |
| `/Users/apple/parallel-work/ledplayserver_py_source/ui/language.py` | All original field names in English |

Original DB schema inferred from `db_operation.py`:
- `custom_info`: `custom_id, phone_num, name, public, time_left, pwd, card_id`
- `recharge_record`: `id, custom_id, money, game_time, date`
- `bind_card_record`: `id, custom_phone, action, card_id, date`
- `ledplay_login`: `id, name, password`

Our `database.py` ports all of this to SQLite with 4 new tables added.

---

---

## Phase 2 — Extended Schema, Data Migration & Advanced Features

*This section is work for a future agent. Do not implement in Phase 1.*

---

### Original Database Analysis

**File:** `/Users/apple/parallel-work/ledplayserver.exe_extracted/led_play_db/ledplaydb_vaibhav.sql`  
Real production MySQL dump from the original Windows kiosk (Dec 2025 → Mar 2026).

**What's in it:**

| Table | Rows | Content |
|-------|------|---------|
| `custom_info` | 2 live (auto_inc at 72) | ~68 players previously deleted, 2 remain: YUV (phone 9643774242) and WERFW |
| `recharge_record` | 31 | Real transactions: ₹0–₹2117, 1–300 min. Shows ₹1499–1500 = 60 min pricing |
| `bind_card_record` | 14 | Card bind/unbind audit. Real card IDs: 10-digit numbers e.g. `2282047570` |
| `game_comsume` | 35 | Game sessions: datetime, minutes consumed, game_group ref, player_group ref |
| `game_group` | 35 | Level files played per session (e.g. `YC05.led`, `DK07.ledb`, `A01.led,A02.led,A03.led`) |
| `player_group` | 35 | Which custom_ids were in each session (comma-separated, e.g. `55,54`) |
| `game_player_group` | 35 | Scores: scode, time_use, pass_time per session |
| `custom_comsume` | 37 | Links custom_id → comsume_id (who played in which session) |
| `ledplay_login` | 1 | admin/admin |
| `game_over`, `part_game_over`, `time_remain` | 0 | Empty — ignore |

**Critical difference — original time model vs new:**

Original: `time_left` float on `custom_info`. Staff adds minutes → game deducts on play. **Deduction model.**  
Our new: `player_sessions` with `expiry_at` clock. **Clock-based model.**

These are incompatible directly. Strategy: import player records + financial history as-is, map gameplay history to `central_scores`. Do NOT try to sync `time_left` into sessions — just zero it out or treat as legacy.

---

### Data Migration Plan (import original data)

Agent should write a one-time migration script: `scripts/migrate_ledplaydb.py`

**Step 1 — Import players (custom_info → custom_info):**
```python
# Direct column map:
# custom_id → custom_id (preserve original IDs 70, 71)
# phone_num → phone_num
# name → name
# public → public
# card_id → card_id
# time_left → time_left (keep for reference, not used in session logic)
# pwd → '' (blank, we don't use passwords)
# Insert with INSERT OR IGNORE (phone_num UNIQUE)
```

**Step 2 — Import recharge_record (as-is):**
```python
# All 31 rows. custom_id refs are historical (most don't exist in custom_info anymore — that's OK).
# Gives financial history for reporting.
```

**Step 3 — Import bind_card_record (as-is):**
```python
# 14 rows. Audit trail, import direct.
```

**Step 4 — Map gameplay history → central_scores:**
```python
# For each game_player_group row:
#   JOIN game_group ON game_group.game_group_id = game_player_group.game_group
#   JOIN player_group ON player_group.player_group_id = game_player_group.player_group
#   JOIN custom_comsume ON custom_comsume.comsume_id = game_comsume.comsume_id
#
# Output per player in player_group.player_info (comma-split):
#   central_scores.player_id = custom_id (int from player_info)
#   central_scores.level = game_group.member_info.split(',')[0]  # first level file
#   central_scores.score = game_player_group.scode
#   central_scores.time_used = game_player_group.time_use
#   central_scores.played_at = game_player_group.pass_time
#   central_scores.game = infer from level filename:
#       YC*.led / DK*.ledb → "climb"
#       A*.led / B*.led    → "climb"
#       *.led (hoops naming) → "hoops"   ← check actual filenames
#   INSERT OR IGNORE (UNIQUE constraint on game+card_id+level+played_at+score)
```

---

### New Tables for Phase 2

Add these tables to `database.py → _ensure_tables()`:

```sql
-- B2B company accounts
CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    contact_name TEXT,
    contact_phone TEXT,
    contact_email TEXT,
    notes        TEXT,
    created_at   TEXT
);

-- Organizational groups (school visits, corporate teams, birthday parties)
CREATE TABLE IF NOT EXISTS org_groups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    company_id   INTEGER,   -- nullable: individual groups have no company
    visit_date   TEXT,
    notes        TEXT,
    created_at   TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

-- Players belong to org groups (many-to-many)
CREATE TABLE IF NOT EXISTS group_members (
    group_id     INTEGER NOT NULL,
    player_id    INTEGER NOT NULL,
    PRIMARY KEY (group_id, player_id)
);
```

Also add to `custom_info` (via ALTER TABLE if upgrading):
```sql
ALTER TABLE custom_info ADD COLUMN company_id INTEGER;
ALTER TABLE custom_info ADD COLUMN date_of_birth TEXT;
ALTER TABLE custom_info ADD COLUMN created_at TEXT;
```

---

### Lifetime Stats & Analytics Views

Create these as SQL views (or computed on query) in `database.py`:

```sql
-- Per-player lifetime stats across all games
CREATE VIEW IF NOT EXISTS v_player_lifetime_stats AS
SELECT
    ci.custom_id AS player_id,
    ci.name,
    ci.phone_num AS phone,
    COUNT(cs.id)                   AS games_played,
    COALESCE(SUM(cs.score), 0)     AS total_score,
    COALESCE(MAX(cs.score), 0)     AS best_score,
    COALESCE(AVG(cs.score), 0)     AS avg_score,
    COALESCE(SUM(cs.time_used), 0) AS total_minutes_played,
    MIN(cs.played_at)              AS first_played,
    MAX(cs.played_at)              AS last_played,
    (SELECT cs2.game FROM central_scores cs2
     WHERE cs2.player_id = ci.custom_id
     GROUP BY cs2.game ORDER BY COUNT(*) DESC LIMIT 1) AS favourite_game
FROM custom_info ci
LEFT JOIN central_scores cs ON cs.player_id = ci.custom_id
GROUP BY ci.custom_id;

-- Per-game leaderboard with player name
CREATE VIEW IF NOT EXISTS v_game_leaderboard AS
SELECT
    cs.game,
    cs.player_id,
    ci.name AS player_name,
    MAX(cs.score)  AS best_score,
    SUM(cs.score)  AS total_score,
    COUNT(cs.id)   AS plays,
    MAX(cs.played_at) AS last_played
FROM central_scores cs
LEFT JOIN custom_info ci ON ci.custom_id = cs.player_id
GROUP BY cs.game, cs.player_id
ORDER BY cs.game, best_score DESC;

-- Session statistics per player
CREATE VIEW IF NOT EXISTS v_player_session_stats AS
SELECT
    ps.player_id,
    ci.name,
    COUNT(ps.id)                    AS total_sessions,
    SUM(ps.duration_min)            AS total_minutes_purchased,
    AVG(ps.duration_min)            AS avg_session_duration,
    MIN(ps.issued_at)               AS first_session,
    MAX(ps.issued_at)               AS last_session,
    COUNT(CASE WHEN ps.closed_at IS NOT NULL THEN 1 END) AS completed_sessions
FROM player_sessions ps
LEFT JOIN custom_info ci ON ci.custom_id = ps.player_id
GROUP BY ps.player_id;
```

---

### New API Endpoints for Phase 2

Add to `api/main.py`:

```python
# Companies
GET  /companies               # list all
POST /companies               # create
GET  /companies/{id}          # detail + member players
PUT  /companies/{id}          # update
DELETE /companies/{id}

# Org Groups
GET  /groups                  # list
POST /groups                  # create (name, company_id?, visit_date?)
GET  /groups/{id}             # detail + members
POST /groups/{id}/members     # add player
DELETE /groups/{id}/members/{player_id}

# Analytics
GET  /analytics/lifetime/{player_id}   # full lifetime stats for one player
GET  /analytics/leaderboard            # game + period filters (already exists in /dashboard/leaderboard)
GET  /analytics/top-players?game=&limit=  # top N per game
GET  /analytics/revenue?from=&to=     # sum of recharge_record.money in date range
GET  /analytics/active-now            # players with active session right now
```

---

### New Frontend Screens for Phase 2

| Screen | Route | What it shows |
|--------|-------|--------------|
| Company Admin | `/companies` | List + create companies, view member players |
| Group Admin | `/groups` | Create visit groups, assign players |
| Player Profile | `/players/:id` | Full history: sessions, scores, recharge history, lifetime stats |
| Analytics | `/analytics` | Revenue chart, top players per game, daily/weekly/monthly play counts |
| Active Now | sidebar widget | Live: which players have active sessions right now |

---

---

### Credit-Based Time System (Core Business Model)

This is the most important Phase 2 concept. Understand this before designing any schema.

**How it works:**

```
Customer pays money
    → Money is converted to TIME CREDITS (minutes)
    → Credits sit on a MASTER ACCOUNT (the payer)
    → Master account distributes time to one or more RFID cards
    → Each card draws from the allocated time when used at a game machine
    → Game machine calls /validate?card_id=XXX → server checks remaining time
```

**Real example:**
- Vaibhav comes in with his family (4 people, 4 RFID cards)
- Pays ₹6000 → gets 240 minutes credit
- Assigns 60 min to Card A (himself), 60 min to Card B (wife), 60 min to Card C (kid 1), 60 min to Card D (kid 2)
- Each person plays independently on their own card
- All 4 cards deduct from Vaibhav's original ₹6000 purchase
- Staff can see: Vaibhav's account spent 240 min total, breakdown per card

**Another example:**
- Corporate team of 10 people
- Company account pre-purchased 600 minutes
- Staff assigns 60 min to each of 10 RFID cards on the day
- Usage tracked per card, total tracked against company account

---

### Rethought Schema for Credit System

Current `player_sessions` + `custom_info.time_left` does NOT support this. Needs new layer.

**New tables:**

```sql
-- Master account (the payer / credit holder)
-- One account can fund many cards
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_player_id INTEGER NOT NULL,  -- custom_info.custom_id of account holder
    name            TEXT,              -- e.g. "Vaibhav Family", "TechCorp Team"
    company_id      INTEGER,           -- optional: links to companies table
    credit_balance  REAL DEFAULT 0,    -- current minutes remaining (across ALL cards on this account)
    created_at      TEXT,
    notes           TEXT,
    FOREIGN KEY (owner_player_id) REFERENCES custom_info(custom_id)
);

-- Financial top-up events (money in → time added to account)
-- Replaces / extends original recharge_record
CREATE TABLE IF NOT EXISTS account_topups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL,
    amount_money    REAL,              -- money paid (rupees, USD, etc.)
    minutes_added   REAL NOT NULL,     -- time credits added
    currency        TEXT DEFAULT 'INR',
    payment_method  TEXT,              -- cash, card, UPI, etc.
    receipt_ref     TEXT,              -- optional receipt/invoice number
    performed_by    TEXT,              -- staff member who processed
    created_at      TEXT,
    notes           TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Time allocated FROM account TO a specific RFID card
-- One account → many card_allocations
CREATE TABLE IF NOT EXISTS card_allocations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL,
    card_id         TEXT NOT NULL,     -- RFID card number
    player_id       INTEGER,           -- optional: which player holds this card
    minutes_allocated REAL NOT NULL,   -- minutes given to this card from account
    minutes_used    REAL DEFAULT 0,    -- updated as card is used (computed from game sessions)
    allocated_at    TEXT,
    expires_at      TEXT,              -- optional expiry for this card's allocation
    allocated_by    TEXT,              -- staff member
    notes           TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Actual time consumed per game session (per card, per game machine)
-- This is what gets written when a game completes
CREATE TABLE IF NOT EXISTS game_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id         TEXT NOT NULL,
    player_id       INTEGER,
    account_id      INTEGER,
    allocation_id   INTEGER,           -- which card_allocation this deducted from
    game            TEXT NOT NULL,     -- hoops, climb, led_hex, laser, grid
    level           TEXT,
    score           REAL DEFAULT 0,
    score2          REAL DEFAULT 0,    -- 2P second player score
    life            INTEGER,
    result          INTEGER,           -- 0=died, 1=completed, etc.
    minutes_used    REAL,              -- actual time consumed this session (game_time)
    played_at       TEXT,
    polled_at       TEXT,              -- when poller picked this up
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    UNIQUE(game, card_id, level, played_at, score)
);

-- Full RFID card bind/unbind audit trail (preserve original + ongoing)
CREATE TABLE IF NOT EXISTS card_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER,
    phone_num       TEXT,
    card_id         TEXT NOT NULL,
    action          TEXT NOT NULL,     -- 'bind', 'unbind', 'allocate', 'expire'
    account_id      INTEGER,
    performed_by    TEXT,
    event_at        TEXT,
    notes           TEXT
);
```

**Key logic:**
- When staff tops up: INSERT account_topups + UPDATE accounts.credit_balance += minutes_added
- When staff allocates to card: INSERT card_allocations + UPDATE accounts.credit_balance -= minutes_allocated
- When game completes (poller): INSERT game_sessions + UPDATE card_allocations.minutes_used += minutes_used
- `/validate?card_id=XXX`: check card_allocations WHERE card_id=XXX AND minutes_used < minutes_allocated AND (expires_at IS NULL OR expires_at > now)

**Replace `player_sessions` for game-side validation:**
Current `player_sessions` uses clock-based expiry. New model: card_allocations is the source of truth for "can this card play?". The two can coexist — `player_sessions` for clock-based Mode 1 (staff issues timed sessions), `card_allocations` for credit-based Mode 2 (balance drawn down per game).

---

### Full Data Preservation Plan

**Import ALL original tables as-is + enrich going forward.**

Preserve these tables in SQLite exactly (keep original column names):

```sql
-- KEEP original: custom_info, recharge_record, bind_card_record, ledplay_login
-- Already in current database.py ✓

-- ADD: preserve original gameplay tables (currently not in our schema)
CREATE TABLE IF NOT EXISTS game_comsume (
    comsume_id  INTEGER PRIMARY KEY,
    time        TEXT NOT NULL,         -- datetime of session
    game_time   REAL NOT NULL,         -- minutes consumed
    game_group  INTEGER NOT NULL,
    player_group INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS game_group (
    game_group_id INTEGER PRIMARY KEY,
    num           INTEGER NOT NULL,    -- score achieved
    player_num    INTEGER,             -- number of players
    game_lever    INTEGER,             -- difficulty level
    member_info   TEXT NOT NULL        -- level filenames played e.g. "YC05.led,YC06.led"
);

CREATE TABLE IF NOT EXISTS player_group (
    player_group_id INTEGER PRIMARY KEY,
    player_num      INTEGER NOT NULL,
    player_info     TEXT NOT NULL      -- comma-separated custom_ids e.g. "55,54"
);

CREATE TABLE IF NOT EXISTS game_player_group (
    game_group   INTEGER NOT NULL,
    game_lever   INTEGER NOT NULL,
    time_use     REAL NOT NULL,
    pass_time    TEXT NOT NULL,        -- datetime result recorded
    player_group INTEGER NOT NULL,
    scode        INTEGER NOT NULL      -- score
);

CREATE TABLE IF NOT EXISTS custom_comsume (
    custom_id    INTEGER NOT NULL,     -- player
    comsume_id   INTEGER NOT NULL,     -- game session
    member       INTEGER NOT NULL,
    game_time    REAL NOT NULL,
    comsume_time REAL NOT NULL
);
```

**Migration script** (`scripts/migrate_ledplaydb.py`) imports all rows from the SQL dump into these tables. Then going forward, new game sessions write to BOTH `game_sessions` (new, rich) AND `game_player_group` / `custom_comsume` (for backward compat reporting).

**Original recharge_record → account_topups mapping:**
```python
# For each row in recharge_record:
#   Find/create account for custom_id
#   INSERT account_topups(account_id, amount_money=money, minutes_added=game_time, created_at=date)
#   UPDATE accounts.credit_balance += game_time
# This reconstructs the financial history in the new credit system
```

**Original bind_card_record → card_events mapping:**
```python
# For each row in bind_card_record:
#   action: 1 = 'bind', 0 = 'unbind'
#   INSERT card_events(phone_num=custom_phone, card_id=card_id, action=action, event_at=date)
```

---

### UI Design Direction

Current frontend is functional but bare (dark theme, basic tables). User wants it better.

**Design principles for next agent:**
- Still dark theme (arcade context, low-light environment)
- Reception desk = fast, minimal clicks. Staff should register + issue session in under 30 seconds
- Dashboard = data-rich, at-a-glance. Cards with numbers, not just tables
- Player profile = full story: account balance, cards linked, game history timeline, money spent
- Account view = credit balance prominently displayed, top-up button always visible, cards listed with individual balances

**Priority UI improvements:**

1. **Reception Desk** — add account balance display prominently. Show remaining credit on card when scanned/searched. One-click "Assign time to card" from account balance.

2. **Player/Account Profile page** — currently missing. Must show:
   - Account credit balance (large, prominent)
   - List of RFID cards on this account + time remaining per card
   - Top-up history (date, money, minutes)
   - Game play history timeline (which game, score, when)
   - Total money spent, total time played

3. **Dashboard** — add:
   - Revenue today / this week / this month (sum of account_topups.amount_money)
   - Active cards right now (card_allocations with remaining time)
   - Top players this month with their game breakdown

4. **Card management** — dedicated screen: scan/enter card ID → see which account it's on, current balance, full usage history

5. **Suggested UI stack upgrade:** Add `recharts` for revenue/usage charts. Add `date-fns` for date formatting. Keep React + Vite (no framework change).

---

### Phase 2 Agent Prompt

```
You are adding Phase 2 features to the Activerse RFID server — a credit-based time management
system for an LED floor game kiosk. Read the FULL playbook before writing any code.

Read first (in order):
1. /Users/apple/activerse_final_changes/activerse-rfid/AGENT_PLAYBOOK.md — FULL spec, schema, UI direction
2. /Users/apple/activerse_final_changes/activerse-rfid/api/database.py — existing DB layer
3. /Users/apple/activerse_final_changes/activerse-rfid/api/main.py — existing endpoints
4. /Users/apple/parallel-work/ledplayserver.exe_extracted/led_play_db/ledplaydb_vaibhav.sql — original DB dump (31 real transactions, 35 game sessions)

Phase 1 (basic RFID server) must already be running. Verify: python3 -m api.main starts without error.

CORE CONCEPT — Credit System:
Customer pays money → gets time credits on a MASTER ACCOUNT.
Account distributes time to one or more RFID cards.
Cards draw down from their allocation when used at game machines.
One person can fund multiple cards (family, team, corporate).

Your tasks (do in order):

SCHEMA (database.py):
1. Add tables: accounts, account_topups, card_allocations, game_sessions, card_events
2. Add tables: companies, org_groups, group_members
3. Add preserved original tables: game_comsume, game_group, player_group, game_player_group, custom_comsume
4. Add columns to custom_info: company_id, date_of_birth, created_at
5. Add SQL views: v_player_lifetime_stats, v_game_leaderboard, v_player_session_stats

DATA MIGRATION (scripts/migrate_ledplaydb.py):
6. Import original 2 players (custom_info rows 70, 71)
7. Import all 31 recharge_record rows → also create accounts + account_topups for each
8. Import all 14 bind_card_record rows → card_events table
9. Import all 35 game sessions (game_comsume + game_group + player_group + game_player_group + custom_comsume) into original tables + map to game_sessions
10. Verify: python3 scripts/migrate_ledplaydb.py runs without error

API (new modules):
11. accounts.py — create account, top-up (money→minutes), allocate time to card, get balance, get cards on account
12. cards.py — card detail (which account, remaining time, full usage history)
13. companies.py — company CRUD
14. groups.py — org group CRUD + member assignment
15. analytics.py — lifetime stats per player, revenue by date range, active cards now, top players per game
16. Update sessions.py validate_card() to check card_allocations as well as player_sessions

FRONTEND (React + Vite):
17. Account Profile page (/accounts/:id) — credit balance prominent, list of cards + time each, top-up history, play history timeline
18. Card Management screen (/cards) — scan/enter card → see account, balance, history
19. Company Admin screen (/companies)
20. Group Admin screen (/groups)
21. Analytics screen (/analytics) — revenue chart (recharts), top players, active now
22. Improve Reception Desk — show account balance when player searched, one-click allocate time to card
23. Install: npm install recharts date-fns (for charts and date formatting)

TESTING:
24. Create account, top-up 120 min, allocate 60 min to card A and 60 min to card B
25. GET /validate?card_id=A → valid, 60 min remaining
26. GET /analytics/lifetime/70 → returns games_played, total_score, best_score, favourite_game
27. GET /analytics/revenue?from=2025-12-01&to=2026-04-01 → sum of imported recharge data
28. Account profile page shows correct balance, cards, and play history

Tech stack: FastAPI + SQLite, React + Vite. No TypeScript, no Next.js, no cloud.
Original DB SQL: /Users/apple/parallel-work/ledplayserver.exe_extracted/led_play_db/ledplaydb_vaibhav.sql
Target DB: /Users/apple/activerse_final_changes/activerse-rfid/data/rfid.sqlite
API port: 9000. Frontend port: 5174.
```

---

## Agent Prompt (copy-paste to start)

```
You are completing the Activerse RFID server — a FastAPI + React admin panel for an LED floor game kiosk.

Read these files FIRST before writing any code:
1. /Users/apple/activerse_final_changes/activerse-rfid/AGENT_PLAYBOOK.md — full spec and current state
2. /Users/apple/activerse_final_changes/activerse-rfid/api/main.py — all endpoints
3. /Users/apple/activerse_final_changes/activerse-rfid/api/database.py — DB layer
4. /Users/apple/activerse_final_changes/activerse-rfid/api/players.py — player CRUD
5. /Users/apple/activerse_final_changes/activerse-rfid/api/sessions.py — session logic
6. /Users/apple/parallel-work/ledplayserver_decompiled/db_operation.py — original SQL reference

Repo: /Users/apple/activerse_final_changes/activerse-rfid/
Backend port: 9000. Frontend port: 5174 (Vite).

What is already DONE (do not rebuild):
- All FastAPI endpoints (players, sessions, validate, dashboard, auth)
- Full SQLite database layer
- All 10 frontend screens (Login, ReceptionDesk, RegisterPlayer, PlayerAdmin, Dashboard, Settings, etc.)

What you need to BUILD (priority order):
1. Verify backend runs: cd /Users/apple/activerse_final_changes/activerse-rfid && python3 -m api.main
2. Verify frontend runs: cd frontend && npm install && npm run dev
3. Fix any import errors or startup crashes
4. Add GET /scores?since= endpoint to each game API (see playbook Step 1)
5. Add led-grid (Floor Is Lava) to GAME_REGISTRY in config.py (port 8004)
6. Add search_recharge_tb_by_id to database.py and expose recharge history in player detail
7. Add DELETE /players/{id} endpoint + delete button in PlayerAdmin.jsx
8. Add Edit player modal in PlayerAdmin.jsx (PUT /players/{id})
9. Run all 13 test steps from the playbook

Tech stack: FastAPI + SQLite (no MySQL needed for dev), React + Vite, no TypeScript, no Vercel, no cloud.
Do not use Vercel, Next.js, or cloud deployment.
```
