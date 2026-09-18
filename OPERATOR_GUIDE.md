# Activerse RFID — Operator Guide

Reception desk daily use. No development commands.

## Start

1. Double-click **`START_SERVER.bat`**.
2. Wait until you see **ACTIVERSE RFID is running**.
3. The browser opens in **fullscreen kiosk** at **http://127.0.0.1:5180/**.
4. **Ctrl+Shift+K** exits fullscreen only (the server keeps running). Use **`STOP_SERVER.bat`** to stop.
5. Leave the minimized service windows open.

**Engineers / debug:** use `scripts/start-dev.sh` (normal browser, Vite dev server — not kiosk).

## Stop

1. Double-click **`STOP_SERVER.bat`**.

## Addresses

- Reception UI: <http://localhost:5180>
- API: <http://localhost:9000>

## First time on this PC

Ask tech to run **`SETUP_FIRST_TIME.bat`**, then edit `.env` with the real game PC IPs and a strong `ADMIN_PASSWORD`.

## Common fixes

### Start says .env missing

Copy `.env.example` to `.env` and set the five `*_API=` lines to the game machines' LAN IPs.

### Browser page blank / won't load

Wait 10–15 seconds after start, then refresh. Or run `STOP_SERVER.bat`, then `START_SERVER.bat` again.

### Games cannot scan cards

On each game PC, `frontend\.env` must point at this RFID PC, e.g.:
`VITE_RFID_API_URL=http://192.168.1.106:9000`

### Leaderboard empty

Confirm game machines are running and `.env` IPs/ports match the live game APIs.

## Packaging / updates

- Download the latest release zip from **GitHub Releases** (operators do not need git).
- Extract the zip to a folder on the PC.
- Double-click **`Activerse RFID.exe`** (or **`START_SERVER.bat`** — both start the server the same way).
- **First time on a new PC:** a technician runs **`SETUP_FIRST_TIME.bat`** once to install Python packages and frontend dependencies. The PC must already have **Python 3.11**, **Node.js LTS**, and **Chrome or Edge** installed.
- **Updates:** stop the server with `STOP_SERVER.bat`, then replace the folder with the new release zip (or drop in the new `Activerse RFID.exe`).
