# Onsite Setup Prompt — Activerse RFID Server (Reception Desk Machine)

You are running on the **physical reception-desk Windows PC** (Machine 6 of 6 in this
deployment). This repo (`activerse-rfid`) was just unzipped onto this machine. It is a
FastAPI + React central server: player registry, RFID card validate, session/credit
CRUD, cross-game score polling, admin dashboard, public leaderboard. **There is no LED
hardware and no hardware driver code in this repo** — this machine only talks to the
other 5 game machines over the LAN via HTTP.

Your job: get this server running, correctly configured to reach all 5 game machines,
and prove it end-to-end with a real card scan. Do not touch any of the 5 game repos —
they are separate machines/checkouts and out of scope.

## Step 0 — Read these two files first, in this order

1. **`ONSITE_LAN_INTEGRATION_PLAN.md`** (repo root) — the network layer: static IP
   scheme for all 6 machines, the port map, the Windows Firewall rules, the exact
   `.env` template with placeholders for the 5 game machines' IPs, and the
   connectivity test you'll run in Step 5. This is the current source of truth for
   cross-machine networking.
2. **`AGENT_PLAYBOOK.md`** (repo root) — existing setup/run instructions, current code
   state, DB schema, and per-game details. Note: its example commands are written in
   Unix shell (`python3`, `&` backgrounding). **You are on Windows** — see the note
   below on translating those commands.

If anything in this prompt conflicts with what you read in those two files, trust the
files (they're the detailed source of truth) — this prompt is just the checklist and
ordering.

**Windows vs. the docs' example commands:** `AGENT_PLAYBOOK.md`'s "How to Run" section
uses `python3` / `pip3` and bare `&` job-backgrounding, which is Unix shell syntax. On
this Windows machine:
- Use `python` (not `python3`) and `pip` (not `pip3`) — confirm which resolves correctly
  with `python --version` first; if this machine only has `py`, use `py -m api.main`.
- Use PowerShell, not bash. Run the backend and frontend in **two separate terminal
  windows/tabs** (or `Start-Process powershell -ArgumentList '-NoExit','-Command','...'`
  from one PowerShell window) rather than trailing `&` — PowerShell's `&` is the call
  operator, not a job-backgrounding suffix.
- Keep the actual commands (`-m api.main`, `npm install`, `npm run dev`, the endpoint
  paths, ports, `.env` keys) exactly as documented in `AGENT_PLAYBOOK.md` and
  `ONSITE_LAN_INTEGRATION_PLAN.md` — only the shell syntax around them changes.

## Steps

### (a) Install backend dependencies
```powershell
cd <repo-root>
pip install -r requirements.txt
```
(or `python -m pip install -r requirements.txt` if `pip` isn't on PATH directly.)

### (b) Install frontend dependencies
```powershell
cd frontend
npm install
```

### (c) Create the real `.env` file
Per `ONSITE_LAN_INTEGRATION_PLAN.md`'s template, create `.env` in the **repo root**
(not in `frontend/`) with the **actual real IPs of the 5 game machines** — get these
from whoever is running the onsite network setup, do NOT leave them as `localhost`:
```env
ADMIN_PASSWORD=<set a real password before going live>
HOOPS_API=http://<hoops-machine-ip>:8000
LASER_API=http://<laser-machine-ip>:8001
CLIMB_API=http://<climb-machine-ip>:8002
GRID_API=http://<grid-machine-ip>:8003
LED_HEX_API=http://<hexagon-machine-ip>:8004
DEFAULT_SESSION_MINUTES=60
MIN_MINUTES_TO_START=5
POLL_INTERVAL_SECONDS=120
DB_PATH=./data/rfid.sqlite
API_HOST=0.0.0.0
API_PORT=9000
```
**Important:** confirm the actual port each game machine is really listening on by
asking whoever set up that machine, or by curling it directly — `AGENT_PLAYBOOK.md`
and `ONSITE_LAN_INTEGRATION_PLAN.md` show slightly different port assignments for
laser/climb/grid/hexagon in their example tables (8001-8004 mapped to different games
in each doc). Don't assume — verify against what's actually running on each machine,
then put the *actual* IP:port into the matching env var above (the var name must match
the game: `HOOPS_API`, `LASER_API`, `CLIMB_API`, `GRID_API`, `LED_HEX_API` — these keys
are fixed in `api/config.py`'s `GAME_REGISTRY`, only the URL values change per site).

This repo's own frontend defaults to `http://localhost:9000` for its own API calls
(`frontend/src/api.js`) — since backend and frontend both run on this same machine,
you do **not** need a `frontend/.env` override here. Leave that as-is.

### (d) Start the backend and frontend
In one PowerShell window:
```powershell
cd <repo-root>
python -m api.main
```
Confirm it prints startup logs and does not crash, and that `http://localhost:9000/health`
returns `{"status":"ok","service":"activerse-rfid"}`.

In a second PowerShell window:
```powershell
cd <repo-root>\frontend
npm run dev
```
Confirm the URL it prints (defaults to port 5178 per the LAN plan's port map, but Vite
may pick a different free port — use whatever it actually prints) loads a login screen
in a browser.

### (e) Run the connectivity test
From `ONSITE_LAN_INTEGRATION_PLAN.md`'s "Connectivity test" section — from this
machine, curl each of the 5 game machines' `/health` endpoint using the real IPs you
put in `.env`:
```powershell
curl http://<hoops-ip>:8000/health
curl http://<laser-ip>:8001/health
curl http://<climb-ip>:8002/health
curl http://<grid-ip>:8003/health
curl http://<hexagon-ip>:8004/health
```
Each must return `{"status":"ok",...}`. If any fails, follow the plan's troubleshooting
order: `ping` the IP first (network/cabling), then check the firewall rule on the
**target** machine (the plan's `New-NetFirewallRule` command) — this is the single most
common cause of "works on localhost, fails over LAN."

Also confirm the reverse direction: from one game machine, `curl http://<this-machine-ip>:9000/health`
should succeed (you may need someone at that machine to run it, or SSH/remote in).

### (f) End-to-end test with a real card
1. Register a test player: `POST /players` with `{"name":"Test Agent","phone":"<unique test number>"}`.
2. Bind a real test RFID card to that player: `POST /players/{id}/bind-card` with
   `{"card_id":"<the real card's ID>"}` (card ID must be more than 5 characters — this
   is enforced).
3. Issue a session: `POST /sessions` with `{"player_id":<id>,"duration_min":30}`. Confirm
   the response includes `expiry_at` and `minutes_remaining`.
4. Confirm `/validate` works locally: `GET /validate?card_id=<the card id>` → expect
   `{"valid":true,"player_name":"Test Agent","session_id":...,"minutes_remaining":...}`.
5. Have someone physically scan that same card at one of the 5 game machines' login
   screen. Confirm the player's real name/badge shows there (not a "could not reach
   RFID server" error) — this proves that game machine can reach this server over the
   LAN, not just that this server works standalone.
6. Play a short session on that game machine (or simulate one if it just registers a
   score), then either wait for the next poll cycle (`POLL_INTERVAL_SECONDS`, default
   120s) or force it immediately: `POST /internal/poll-now`. Confirm the resulting
   score appears in this server's leaderboard: `GET /dashboard/leaderboard`.

## Reporting back

For each step (a)–(f), report a specific **pass/fail**, not just "done" — e.g. "(e)
FAIL: Climb machine (192.168.1.103:8002) timed out, ping succeeded, so it's a firewall
rule missing on the Climb machine" rather than "connectivity test done." If something
fails, state which step, which machine/IP, and the exact error text or response you
got, so it can be triaged without re-running everything from scratch.
