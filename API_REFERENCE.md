# API Reference — Activerse RFID Server

Lightweight endpoint reference for `api/main.py`. Not a full OpenAPI spec — for exact
schemas see `api/models.py`, or run the server and check `http://localhost:9000/docs`
(FastAPI's auto-generated Swagger UI) for live, complete request/response shapes.

All endpoints are under the server root (default `http://localhost:9000`, or the
real LAN IP:9000 onsite). CORS is wide open (`allow_origins=["*"]`) — this is a closed
LAN app, not internet-facing.

## Root

- **`GET /health`** — liveness check for this server. No params.
  Response: `{status: "ok", service: "activerse-rfid"}`.

---

## Auth

- **`POST /auth/login`** — admin login check.
  Body: `{username, password}`.
  Response: `{success: true}` or `{success: false, error}`. (If no admin row exists yet,
  `verify_login` returns `true` unconditionally — first-run bootstrap behavior.)

- **`POST /auth/change-password`** — overwrite the single admin credential row.
  Body: `{username, password}`.
  Response: `{success: true}`.

---

## Settings

- **`GET /settings`** — fetch all global key/value settings (e.g. money/time ratios).
  Response: flat `{key: value, ...}` dict (values stored as strings).

- **`PUT /settings`** — upsert one or more global settings.
  Body: arbitrary `{key: value, ...}` dict — each key is upserted individually.
  Response: the full updated settings dict.

- **`PUT /games/{game_key}/settings`** — push difficulty/session-length defaults to a
  specific game machine's own `/settings` endpoint (proxies over HTTP to that game's
  API), and records what was pushed locally.
  Path: `game_key` — one of `hoops`, `laser`, `climb`, `grid`, `led_hex` (must exist in
  `GAME_REGISTRY`, else `404`).
  Body: `{default_difficulty: str, session_minutes: int}`.
  Response: `{success: true}`. Errors: `404` unknown game key, `502` if the target game
  machine couldn't be reached.

- **`GET /games/{game_key}/settings`** — read back the last settings pushed to a game
  (from this server's local record, not a live query of the game machine).
  Response: `{game, default_difficulty, session_minutes, pushed_at}` or `{}` if never pushed.

---

## Players

- **`GET /players?q=`** — list/search players. `q` optional; blank returns all.
  Response: array of player summaries: `{id, phone, name, email, age, public, card_id,
  notes, time_left, credit_balance}`.

- **`POST /players`** — register a new player. Phone number is the uniqueness key.
  Body: `{name, phone, email?, age?, public=true, notes?}`.
  Response: full player detail (see `GET /players/{id}` below). Error: `400` if phone
  already registered or empty.

- **`GET /players/{player_id}`** — full player detail.
  Response: player summary fields **plus** `sessions` (this player's session history),
  `scores` (last 50 rows from `central_scores`), and `recharge_history` (top-up log).

- **`PUT /players/{player_id}`** — update editable profile fields (not phone).
  Body: `{name?, email?, age?, public?, notes?}` — all optional, only provided fields change.
  Response: updated player detail (same shape as `GET /players/{id}`).

- **`DELETE /players/{player_id}`** — delete a player record.
  Response: `{success: true}`.

- **`POST /players/{player_id}/bind-card`** — bind an RFID card to a player.
  Body: `{card_id}` (must be >5 characters). Rejects if the card is already bound to a
  *different* player, or if the player has an active session on their current card
  (must close it first). Response: `{success: true, card_id}`.

- **`POST /players/{player_id}/unbind-card`** — remove the card binding. Rejects if the
  player has an active session (close it first), or if no card is currently bound.
  Response: `{success: true}`.

- **`POST /players/{player_id}/topup`** — add prepaid minutes (and optionally record a
  money amount) to a player's credit balance.
  Body: `{minutes, amount_money?}` (`minutes` must be > 0).
  Response: `{success: true, credit_balance}` (new balance after top-up).

---

## Sessions

Session model is clock-based: issuing a session deducts the full duration from the
player's credit balance up front (no refund on early close or unused expiry).

- **`POST /sessions`** — issue a new session for a player. Requires a bound RFID card;
  seeds the payer onto `session_roster`. Deduct + create + roster seed are atomic.
  Body: `{player_id, duration_min=60, notes?}`.
  Response: `{session_id, player_id, card_id, issued_at, expiry_at, duration_min,
  minutes_remaining, credit_balance_after, roster}`. Error: `400` if no card bound,
  insufficient credit, or player already on an open session/roster; `404` if player
  not found.

- **`GET /sessions/active`** — list all currently-open sessions.
  Response: array of session rows, each with `minutes_remaining`, `roster`, and
  `roster_count` computed live.

- **`GET /sessions/{session_id}`** — single session detail.
  Response: session row + `minutes_remaining` + `adjustments` + `roster`.

- **`GET /sessions/{session_id}/roster`** — team members for score attribution
  (total ÷ N on poll). Response: `{session_id, roster: [{player_id, name, phone,
  is_payer}]}`.

- **`POST /sessions/{session_id}/roster`** — add a player to the session roster.
  Body: `{player_id}`. Rejects if the player is already on another open roster/session.
  Response: `{success: true, session_id, roster}`.

- **`DELETE /sessions/{session_id}/roster/{player_id}`** — remove a non-payer roster
  member. Cannot remove the session holder. Response: `{success: true, session_id, roster}`.

- **`POST /sessions/{session_id}/adjust`** — add or subtract minutes from an active
  session's expiry.
  Body: `{delta_min, reason?, adjusted_by?}` (`delta_min` negative to subtract).
  Response: `{session_id, expiry_at, minutes_remaining}`. Error: `400` if session
  already closed, `404` if not found.

- **`POST /sessions/{session_id}/close`** — close a session early.
  Response: `{success: true, session_id}`. Error: `404` if not found or already closed.

- **`GET /validate?card_id=`** — **called by game machines, no auth.** Checks whether a
  scanned card has an active, non-expired session with enough time to start.
  Response: `{valid: bool, player_name?, session_id?, minutes_remaining?, reason?,
  members?}`. On `valid: true`, `members` is `[{player_id, name}, ...]` (roster at
  validate time; legacy sessions without a roster row are auto-seeded with the payer).
  `reason` values on `valid: false`: `no_card`, `card_not_found`, `no_active_session`,
  `expired`, `insufficient_time`.

---

## Dashboard

- **`GET /dashboard/health`** — last-known status of each of the 5 game machines (as
  recorded by the poller, not a live check). Response: array of `{game, status,
  last_checked, active_game_id}` rows.

- **`GET /dashboard/leaderboard?game=all&period=alltime&limit=20&board=individual`** —
  cross-game score leaderboard. `game` filters to one game key or `all`; `period` is
  `alltime`, `today`, `week`, or `month`; `limit` caps rows (max 100).
  `board=individual` (default) returns per-player share rows from `central_scores`
  (joined with player name), ordered by `final_score`/`score` descending.
  `board=team` returns multi-member runs from `central_team_scores` (`member_count >= 2`)
  with parsed `members` and a joined `player_name` label.

- **`GET /dashboard/stats`** — quick aggregate counters for the admin dashboard.
  Response: `{games_today, games_month, unique_players_today}`.

- **`GET /dashboard/player/{player_id}`** — a player's full activity history for the
  dashboard's player-detail view.
  Response: `{player, sessions, scores, recharge_history}`.

---

## Internal

- **`POST /internal/poll-now`** — force an immediate poll of all 5 game machines'
  `/scores` endpoints, instead of waiting for the next `POLL_INTERVAL_SECONDS` (default
  120s) background cycle. Useful for testing the end-to-end score pipeline without
  waiting. Response: `{success: true}`.

## Companies / Groups (Phase B)

- `GET/POST /companies`, `GET/PUT/DELETE /companies/{id}`
- `GET /groups?company_id=`, `POST /groups`, `GET/PUT/DELETE /groups/{id}`
- `POST /groups/{id}/members` — `{player_id}` or `{name,phone}` (phone dedup into Players)
- `DELETE /groups/{id}/members/{player_id}`
- `PUT /groups/{id}/leader` `{player_id}`
- `POST /groups/{id}/start-visit` `{duration_min, card_id?}` — issue session + load roster + stamp company/group
- `GET /import/template.xlsx`, `POST /import/excel` (multipart file)
- `GET /dashboard/leaderboard?...&company_id=` filters Individual/Team boards
