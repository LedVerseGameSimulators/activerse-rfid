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

## Companies / Groups / Company Membership (Phase B + durable-membership exit)

Core model: `company_members` is the **durable** roster (one company per player,
`UNIQUE(player_id)`) — it survives groups being deleted and remade. `groups` are
**temporary teams** inside one company, or **walk-in groups with no company at all**
(`company_id` is nullable — e.g. a one-off birthday-party team). A player can be on at
most one group at a time (`group_members` is `UNIQUE(player_id)`). Adding a player to a
corporate group auto-joins them to that company; adding them to a walk-in group skips
company checks entirely. While on a group, solo session issuance is blocked — Start
Visit on the group is the only play path; leaving the group re-enables solo play (still
a company member).

- `GET/POST /companies`, `GET/PUT/DELETE /companies/{id}`
  - `DELETE` is blocked (`400`) if the company has an active (open) session.
- `GET /companies/{id}/members` — durable company roster.
  Response: array of `{player_id, name, phone, joined_at, group_id, group_name}` (the
  last two are `null` if the player isn't currently on any group).
- `DELETE /companies/{id}/members/{player_id}` — leave company. Auto-removes them from
  their current group first if they have one and no active session; `400` if they have
  an active session (close it first).
- `GET /groups?company_id=&walk_in_only=` — `company_id` omitted returns all groups
  (corporate + walk-in); `walk_in_only=true` returns only company-less groups.
- `POST /groups` `{company_id?, name, leader_player_id?}` — `company_id` is optional;
  omit/`null` for a walk-in group. Company-scoped groups still enforce unique name per
  company; walk-in group names aren't deduped against anything.
- `GET/PUT/DELETE /groups/{id}`
  - `DELETE` is blocked (`400`) if the group has an active (open) session; on success it
    only drops `group_members` — the player's `company_members` row is untouched.
- `POST /groups/{id}/members` — `{player_id}` or `{name,phone}` (phone dedup into
  Players). `400` if the player already belongs to a different company than the group,
  or is already on a different group.
- `DELETE /groups/{id}/members/{player_id}`
- `POST /groups/{id}/members/transfer` `{player_id}` — atomic move from the player's
  current group into group `{id}` (destination), single transaction (no
  remove-then-add race). `400` if the player is the leader of their current group
  (reassign leadership there first) or belongs to a different company than the
  destination group.
- `PUT /groups/{id}/leader` `{player_id}`
- `POST /groups/{id}/start-visit` `{duration_min, card_id?}` — **all-or-nothing
  preflight**: validates every member (same company as the group if it has one, no
  conflicting open session, leader has enough credit + no card conflict) before writing
  anything. On any failure, `400` with every failing reason listed, and nothing is
  written (no partial session/roster/credit-deduction). On success: issues the session
  on the leader's card, loads all members onto the roster (score split), stamps
  `company_id`/`group_id` (company_id is `null` for a walk-in group).
- `GET /import/template.xlsx`, `POST /import/excel` (multipart file) — legacy global
  import, still wired but no longer used by any UI screen (superseded below).
- `GET /companies/{id}/import/template.xlsx`, `POST /companies/{id}/import/excel`
  (multipart file) — company-scoped import. Columns: `group_name, player_name, phone,
  is_team_leader, email, age`. The company comes from the URL only — a stray
  `company_name` column, if present, is ignored, never creates/targets a different
  company. `group_name` is optional: blank onboards the player into `company_members`
  only (no group), matching "guest list first, teams later". Idempotent — re-uploading
  the same file creates zero duplicate rows. A row for a player already affiliated with
  a different company surfaces as a per-row error, never creates a new company.
- `GET /dashboard/leaderboard?...&company_id=&group_id=` — filters Individual/Team
  boards by company and/or group (e.g. "Team Alpha vs Team Beta" within one company, or
  a walk-in group's own board via `group_id` alone with no `company_id`). A solo session
  by a company member not currently on any group also stamps `company_id` (no
  `group_id`), so they still show up on the company's board.
