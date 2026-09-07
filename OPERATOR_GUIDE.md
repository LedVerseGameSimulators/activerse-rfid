# Activerse RFID — Operator Guide

Reception desk daily use. No development commands.

## Start

1. Double-click **`START_SERVER.bat`**.
2. Browser opens at <http://localhost:5180>.
3. Leave the two minimized windows open.

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

### Games cannot scan cards

On each game PC, `frontend\.env` must point at this RFID PC, e.g.:
`VITE_RFID_API_URL=http://192.168.1.106:9000`

### Leaderboard empty

Confirm game machines are running and `.env` IPs/ports match the live game APIs.
