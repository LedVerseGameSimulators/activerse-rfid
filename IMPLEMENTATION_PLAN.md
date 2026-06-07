# Activerse RFID Server — Implementation Plan

**Repo:** `/Users/apple/activerse_final_changes/activerse-rfid`  
**Original source:** `/Users/apple/parallel-work/ledplayserver_decompiled/`  
**Original source (py):** `/Users/apple/parallel-work/ledplayserver_py_source/`  
**Status:** Repo initialised, nothing built yet.

---

## What this is

Central reception/admin app for the Activerse LED floor game kiosk.  
Sits on a 5th machine (reception PC). Manages players, RFID cards, sessions.  
4 game machines (Hoops, Climb, LED Hex, Laser) each run their own FastAPI stack.

**This server does NOT control game start/stop.** Game machines are autonomous.  
Its only role in gameplay = validate RFID card when player starts a game.

---

## Real-world machine layout

```
Machine 1 (Hoops)    :8000 API  :8765 WS  :5173 UI
Machine 2 (Climb)    :8001 API  :8766 WS  :5174 UI
Machine 3 (LED Hex)  :8002 API  :8767 WS  :5175 UI
Machine 4 (Laser)    :8003 API  :8768 WS  :5176 UI
Machine 5 (RFID)     :9000 API            :5180 UI  ← THIS REPO
```

Dev: all on same machine, localhost.  
Prod: change `GAME_REGISTRY` env vars to actual LAN IPs.

---

## Session model (clock-based, NOT credit deduction)

```
Reception issues card for 60 min:
  expiry_at = NOW() + 60 min
  stored in player_sessions table

Player at game machine:
  picks game → level → difficulty → scans RFID
  game frontend calls: GET http://rfid-server:9000/validate?card_id=X
  RFID server checks: expiry_at - NOW() >= 5 min?
    YES → { valid: true, player_name, session_id, minutes_remaining }
    NO  → { valid: false, reason: "expired" | "insufficient_time" }

Game starts if valid. RFID server sends NOTHING else.
Game machine controls start/stop/scoring completely.

No deduction per game. No refund. Pure clock check.
```

Rules:
- Min 5 minutes remaining required to start any game
- Game is 5 minutes — if less than 5 min left → reject
- Reception CAN add/subtract minutes from active session (extend/reduce expiry_at)

---

## Two gameplay modes (both must work)

**Mode 1 — Anonymous (current, already working)**  
Player types name manually in game frontend.  
No RFID scan. `card_id = null` in scores.  
Keep working as-is. Do not break this.

**Mode 2 — RFID (new)**  
Player scans card → game frontend calls `/validate` → gets player name.  
Score stored with `card_id` → links to master player record.  
Session tracked in `player_sessions`.

---

## Database design

### Dev: SQLite (`data/rfid.sqlite`)  
### Prod: MySQL on Machine 5, credentials from original: host=localhost user=root pwd=root db=ledplaydb

```sql
-- MASTER PLAYER TABLE
CREATE TABLE players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT UNIQUE NOT NULL,   -- unique identifier
    name        TEXT NOT NULL,
    email       TEXT,                   -- optional
    age         INTEGER,                -- optional
    public      INTEGER DEFAULT 1,      -- show on leaderboard
    card_id     TEXT UNIQUE,            -- currently bound RFID tag
    created_at  TEXT,                   -- ISO datetime
    notes       TEXT
);

-- RFID CARD BINDING HISTORY
CREATE TABLE card_bindings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER REFERENCES players(id),
    card_id     TEXT,
    action      INTEGER,   -- 1=bind, 0=unbind
    bound_at    TEXT
);

-- VISIT SESSIONS (one row per visit)
CREATE TABLE player_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id    INTEGER REFERENCES players(id),
    card_id      TEXT,
    issued_at    TEXT,     -- ISO datetime
    expiry_at    TEXT,     -- issued_at + duration
    duration_min INTEGER,  -- e.g. 60
    closed_at    TEXT,     -- null if still active
    notes        TEXT
);

-- RECHARGE / EXTENSION LOG
CREATE TABLE session_adjustments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES player_sessions(id),
    delta_min   INTEGER,   -- positive=add, negative=subtract
    reason      TEXT,
    adjusted_at TEXT,
    adjusted_by TEXT       -- receptionist name
);

-- CENTRALIZED SCORES (polled from game machines every 2 min)
CREATE TABLE central_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id   INTEGER REFERENCES players(id),  -- null if anonymous
    card_id     TEXT,
    session_id  INTEGER REFERENCES player_sessions(id),  -- null if anonymous
    game        TEXT,      -- 'hoops','climb','led_hex','laser'
    level       TEXT,
    score       REAL,
    score2      REAL,      -- P2 in 2P games
    life        INTEGER,
    result      INTEGER,   -- 0=lost 1=complete 2=timeout
    time_used   REAL,
    played_at   TEXT,
    polled_at   TEXT
);

-- GAME HEALTH (updated by poller)
CREATE TABLE game_health (
    game        TEXT PRIMARY KEY,
    status      TEXT,      -- 'running','idle','down'
    last_checked TEXT,
    active_game_id TEXT
);
```

---

## API Endpoints to build

### Players (admin panel)
```
GET    /players                     list all, search by phone/name/card_id
POST   /players                     register new player
GET    /players/{id}                get player + sessions + scores
PUT    /players/{id}                update name/email/age/public/notes
POST   /players/{id}/bind-card      bind RFID card
POST   /players/{id}/unbind-card    unbind current card
```

### Sessions (reception desk)
```
POST   /sessions                    issue new session
  body: { player_id, duration_min=60, notes }
  → creates player_sessions row, expiry_at = NOW() + duration_min

GET    /sessions/active             all currently active sessions
GET    /sessions/{id}               session detail
POST   /sessions/{id}/adjust        add or subtract minutes
  body: { delta_min, reason }       e.g. { delta_min: 30, reason: "comp" }
POST   /sessions/{id}/close         manually close session

GET    /validate                    ← CALLED BY GAME MACHINES
  query: card_id=XXXX
  → find active session for card_id
  → check expiry_at - NOW() >= 5 min
  → return { valid, player_name, session_id, minutes_remaining }
  → NO auth needed, game machines call this
```

### Dashboard
```
GET    /dashboard/health            all 4 games status
GET    /dashboard/leaderboard       top scores across all games
  query: game=all|hoops|climb|led_hex|laser
         period=today|week|month|alltime
         limit=20
GET    /dashboard/stats             games played today/month, unique players
GET    /dashboard/player/{id}       player history: all sessions, all games, scores
```

### Internal
```
POST   /internal/ingest-scores      called by poller, upserts scores from game APIs
GET    /internal/poll-now           manual trigger for debugging
```

---

## Poller (background async task)

Runs every 120s inside the FastAPI process (`asyncio.create_task`).

```python
GAME_REGISTRY = {
    "hoops":   "http://localhost:8000",
    "climb":   "http://localhost:8001",
    "led_hex": "http://localhost:8002",
    "laser":   "http://localhost:8003",
}

async def poller():
    last_polled = {}   # game → last ISO timestamp
    while True:
        for game, url in GAME_REGISTRY.items():
            # 1. health check
            GET {url}/health → update game_health table

            # 2. pull new scores
            since = last_polled.get(game, "2000-01-01")
            GET {url}/scores?since={since}
            → upsert into central_scores
            → join card_id → player_id
            last_polled[game] = NOW()

        await asyncio.sleep(120)
```

**Each game API needs one new endpoint added:**
```
GET /scores?since=2026-06-05T10:00:00
→ SELECT * FROM hex_scores WHERE ts > ? ORDER BY ts ASC
```
Add this to `led-hoops`, `led-climb`, `led-hexagon`, `led-laser` → `api/main.py`.

---

## Frontend screens (React + Vite :5180)

```
App
├── ReceptionDesk       ← default screen (main use)
│   ├── PlayerSearch    search by phone / name / card_id
│   ├── PlayerCard      show player: name, expiry, sessions
│   ├── IssueSession    pick duration, confirm → POST /sessions
│   └── AdjustSession   +/- minutes on active session
│
├── PlayerAdmin         ← manage players
│   ├── PlayerList      table with search/filter
│   ├── RegisterPlayer  form: name*, phone*, email?, age?
│   └── BindCard        enter card_id → bind
│
├── Dashboard           ← view only (staff screen)
│   ├── GameHealth      4 game status tiles (green/red/idle)
│   ├── Leaderboard     cross-game top scores, filter by game/period
│   └── Stats           daily/monthly summary
│
└── Settings            (future: db config, game URLs)
```

---

## Game frontend changes needed (each game)

Add RFID scan step before game start:

```jsx
// In GameSettingsScreen.jsx (each game)
// After picking level + difficulty, before confirming:

const [rfidState, setRfidState] = useState('idle') // idle | scanning | valid | invalid | skipped
const [playerInfo, setPlayerInfo] = useState(null)

// Mode 2: scan card
const handleScan = async (cardId) => {
  const res = await fetch(`http://rfid-server:9000/validate?card_id=${cardId}`)
  const data = await res.json()
  if (data.valid) {
    setPlayerInfo(data)   // { player_name, session_id, minutes_remaining }
    setRfidState('valid')
  } else {
    setRfidState('invalid')  // show error
  }
}

// Mode 1: skip scan (anonymous)
const handleSkip = () => setRfidState('skipped')

// On confirm game start:
// pass player_name (from RFID or typed) to start-game API
```

RFID reader in HID keyboard mode → just capture keypress into a text field (reader auto-types card ID + Enter). No USB/serial code needed.

---

## What to reuse from original source vs build fresh

### PORT DIRECTLY from `/Users/apple/parallel-work/ledplayserver_decompiled/`

| Original file | What to port | Notes |
|---|---|---|
| `db_operation.py` | ALL SQL queries — all `search_*`, `insert_*`, `update_*` methods | Translate MySQL connector → SQLite. Same logic, same column names. |
| `ui_customer_regist.py` | `register()` method — phone uniqueness check, insert custom_info + initial recharge_record | Same logic, wrap in POST /players route |
| `ui_recharge.py` | `recharge()` — `time_left += game_time`, insert recharge_record | Keep recharge_record for accounting history |
| `ui_bindcard.py` | bind/unbind logic — check if card already bound, update custom_info.card_id, insert bind_card_record | Same |
| `ui_main.py` | search queries, display table queries | Same |

### EXISTING DB TABLES — keep exact schema, same names
`custom_info`, `recharge_record`, `bind_card_record` — do NOT rename or restructure.
New tables added alongside. All original queries still work.

### BUILD FRESH (didn't exist in original)
| Thing | Reason |
|---|---|
| `player_sessions` table | Original stored time_left as float minutes. We use expiry_at datetime. Different model. |
| `session_adjustments` table | Didn't exist |
| `central_scores` table | Scores stayed on game machines — no central store |
| `game_health` table | Didn't exist |
| `/validate` endpoint | Original used UDP START command. We use HTTP. |
| Poller (score ingestion) | Original games wrote directly to shared MySQL. Now we poll. |
| React frontend | Original was tkinter desktop app. Full rewrite. |

---

## File structure to build

```
activerse-rfid/
├── api/
│   ├── __init__.py
│   ├── main.py          FastAPI app, all routes
│   ├── config.py        ✅ done — env vars, game registry
│   ├── database.py      SQLite/MySQL wrapper, all table creation
│   ├── models.py        Pydantic request/response schemas
│   ├── players.py       player CRUD logic
│   ├── sessions.py      session issue/adjust/validate logic
│   ├── dashboard.py     leaderboard, stats, health queries
│   └── poller.py        background score ingestion task
├── data/
│   └── rfid.sqlite      (auto-created on startup)
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── screens/
│       │   ├── ReceptionDesk.jsx
│       │   ├── PlayerSearch.jsx
│       │   ├── PlayerAdmin.jsx
│       │   ├── RegisterPlayer.jsx
│       │   ├── BindCard.jsx
│       │   ├── IssueSession.jsx
│       │   ├── AdjustSession.jsx
│       │   └── Dashboard.jsx
│       └── components/
│           ├── GameHealthTile.jsx
│           ├── LeaderboardTable.jsx
│           └── PlayerCard.jsx
├── scripts/
│   └── start-dev.sh
└── requirements.txt
```

---

## What each game API needs added (small change, 4 files)

In each `led-{game}/api/main.py`, add:

```python
@app.get("/scores")
async def get_scores(since: str = "2000-01-01T00:00:00"):
    """Return scores recorded after `since` timestamp. Used by RFID poller."""
    try:
        rows = db.get_scores_since(since)  # add to database.py too
        return {"success": True, "game": GAME_NAME, "scores": rows}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

In each `led-{game}/api/database.py`, add:

```python
def get_scores_since(self, since: str):
    with self._scores_lock:
        con = self._scores_conn()
        rows = con.execute(
            "SELECT card_id, level, score, score2, life, result, time_used, ts "
            "FROM hex_scores WHERE ts > ? ORDER BY ts ASC",
            (since,)
        ).fetchall()
        con.close()
    return [dict(zip(
        ["card_id","level","score","score2","life","result","time_used","ts"], r
    )) for r in rows]
```

Also add `game` column to hex_scores in all games:
```python
# In _ensure_scores_table(), add to ALTER TABLE block:
("game", "TEXT"),
```

And set it on INSERT:
```python
# In record_game_score():
# add game=GAME_NAME to insert
```

---

## Testing steps (in order)

### Step 1: API boots, DB creates
```bash
cd activerse-rfid
pip install fastapi uvicorn python-dotenv loguru httpx
python3 -m api.main
# expect: all tables created, server on :9000
curl http://localhost:9000/health
```

### Step 2: Player registration
```bash
curl -X POST http://localhost:9000/players \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Player","phone":"9999999999"}'
# expect: { id: 1, name, phone, card_id: null }
```

### Step 3: Bind RFID card
```bash
curl -X POST http://localhost:9000/players/1/bind-card \
  -d '{"card_id":"CARD001"}'
# expect: { success: true }
```

### Step 4: Issue session
```bash
curl -X POST http://localhost:9000/sessions \
  -d '{"player_id":1,"duration_min":60}'
# expect: { session_id, expiry_at, minutes_remaining: 60 }
```

### Step 5: Validate card (what game machine calls)
```bash
curl "http://localhost:9000/validate?card_id=CARD001"
# expect: { valid: true, player_name: "Test Player", minutes_remaining: 59 }
```

### Step 6: Adjust session
```bash
curl -X POST http://localhost:9000/sessions/1/adjust \
  -d '{"delta_min":30,"reason":"comp"}'
# expect: new expiry_at = original + 30 min
```

### Step 7: Expire and validate
```bash
# Manually set expiry_at to 2 min from now in DB
curl "http://localhost:9000/validate?card_id=CARD001"
# expect: { valid: false, reason: "insufficient_time", minutes_remaining: 2 }
```

### Step 8: Poller pulls game scores
```bash
# Start any game API (e.g. climb on :8001)
# Play a game, complete it
# Wait 2 min or: curl -X POST http://localhost:9000/internal/poll-now
# Check: curl http://localhost:9000/dashboard/leaderboard
# expect: score appears in central_scores
```

### Step 9: Dashboard health
```bash
# Start all 4 game APIs
bash /Users/apple/activerse_final_changes/scripts/start-all-games.sh
curl http://localhost:9000/dashboard/health
# expect: all 4 games show status
```

### Step 10: Game frontend RFID integration
```bash
# In led-climb frontend, add RFID scan step
# Scan card (type card_id in input field, press Enter)
# Expect: player name auto-fills, session validated
# Start game → score saved with card_id linked
```

---

## Start-all script update (add RFID as 5th service)

Add to `/Users/apple/activerse_final_changes/scripts/start-all-games.sh`:
```bash
echo "==> RFID Server (API:9000 UI:5180)"
cd "$ROOT/activerse-rfid"
python3 -m api.main > "/tmp/rfid-api.log" 2>&1 &
cd frontend && npm run dev -- --port 5180 --strictPort > "/tmp/rfid-ui.log" 2>&1 &
cd "$ROOT"
```

---

## Key decisions already made

| Decision | Value |
|----------|-------|
| Unique player identifier | `phone` (not email, not ID) |
| Optional fields | `email`, `age` |
| Session model | Clock-based. `expiry_at` datetime. No per-game deduction. |
| Min time to start game | 5 minutes remaining |
| Session duration default | 60 min, free-form input |
| Extend/reduce session | Yes — add or subtract minutes, logs in `session_adjustments` |
| Anonymous play (Mode 1) | Keep working. RFID optional. |
| RFID play (Mode 2) | Scan card → `/validate` → get player name |
| RFID reader type | USB HID keyboard emulation — browser text input, no serial code |
| Game control | Game machines fully autonomous. RFID server never sends START/STOP. |
| Score storage | Local SQLite per game + polled into central MySQL every 2 min |
| Poller interval | 120 seconds (configurable via env) |
| DB (dev) | SQLite at `data/rfid.sqlite` |
| DB (prod) | MySQL host=machine5-ip user=root pwd=root db=ledplaydb |

---

## Prompt for new chat

> You are implementing the `activerse-rfid` server — a FastAPI + React admin app for an LED floor game kiosk system.
>
> **Repo:** `/Users/apple/activerse_final_changes/activerse-rfid/`  
> **Read first:**  
> - `/Users/apple/activerse_final_changes/activerse-rfid/IMPLEMENTATION_PLAN.md` — full spec (this file)  
> - `/Users/apple/activerse_final_changes/CLIMB_MIGRATION_PLAYBOOK.md` — context on game stack  
> - `/Users/apple/parallel-work/ledplayserver_decompiled/` — original RFID server source to reference  
>
> **Reference game APIs (already built, DO NOT modify unless adding `/scores?since=` endpoint):**  
> - `led-hoops` :8000, `led-climb` :8001, `led-hexagon` :8002, `led-laser` :8003  
> - All at `/Users/apple/activerse_final_changes/led-{game}/`  
>
> **Build order:**  
> 1. `api/database.py` — SQLite wrapper, create all tables on startup  
> 2. `api/models.py` — Pydantic schemas  
> 3. `api/players.py` — player CRUD  
> 4. `api/sessions.py` — issue/adjust/validate logic  
> 5. `api/main.py` — wire all routes + startup poller  
> 6. `api/poller.py` — background score ingestion  
> 7. `api/dashboard.py` — leaderboard/stats queries  
> 8. Frontend — React Vite, screens per IMPLEMENTATION_PLAN.md  
> 9. Add `/scores?since=` endpoint to all 4 game APIs  
> 10. Test all steps in order per "Testing steps" section  
>
> **Do not use Vercel, Next.js, or any cloud platform. This is a local LAN Python/React app.**  
> **Read the full IMPLEMENTATION_PLAN.md before writing any code.**
