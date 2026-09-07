# AGENT_SETUP_AND_RUN.md — Activerse RFID (Windows reception PC)

**Audience:** an AI coding agent on **the RFID / reception Windows PC**.

## Mandatory first steps (before any install/clone/copy)

1. **Read this entire file** (`AGENT_SETUP_AND_RUN.md`) end to end.  
2. Skim `WINDOWS_ONSITE_HANDOFF.md` / `OPERATOR_GUIDE.md` / `ONSITE_LAN_INTEGRATION_PLAN.md` if present.  
3. **Ask the human** for the OLD on-machine path (or `NONE`).  
4. Clone/pull, audit, then **present results and wait for explicit confirmation**
   before copying `.env`, committing, pushing, or starting the server.

**Hard rule:** no auto-keep of `.env` or auto-push. Wait for human OK.

This repo has **no Git LFS levels**. Game PCs handle `.led`/`.ledb` themselves.

---

## Machine identity

| Item | Value |
|------|-------|
| Repo | `activerse-rfid` |
| Clone URL | `https://github.com/LedVerseGameSimulators/activerse-rfid.git` |
| Suggested path | `C:\activerse\activerse-rfid` |
| API / UI | `9000` / `5180` |
| Start / Stop | `START_SERVER.bat` / `STOP_SERVER.bat` |
| First-time setup | `SETUP_FIRST_TIME.bat` |
| Env | `.env` (from `.env.example`) |

---

## Phase 1 — Ask for OLD path (**deliberately**)

> What is the full path to the **existing / old** Activerse RFID install on this PC?  
> If none, reply `NONE`.

Wait for the answer. Verify path if given. Do not guess.

---

## Phase 2 — Clone `main`

```bat
mkdir C:\activerse 2>nul
cd C:\activerse
git clone https://github.com/LedVerseGameSimulators/activerse-rfid.git
cd activerse-rfid
git checkout main
git pull
```

---

## Phase 3 — Audit (read-only) then **WAIT for confirmation**

Compare OLD vs NEW for `api\`, `frontend\src\`. Note `.env` as a venue candidate only.

Present in chat:

1. NEW tip  
2. `ONLY_ON_MACHINE_CODE` / `DIFFERS_CODE`  
3. Whether OLD `.env` exists (do **not** paste secrets; say “OLD .env present” + list **keys** only)  
4. Numbered proposed actions  
5. Ask: “Confirm which actions to apply. I will not copy/commit/push/start until you confirm.”

Only after confirmation: port approved code and push; copy/create `.env` as approved.

Do not commit `data\*.sqlite` or secrets.

---

## Phase 4–5 — Install / run (after human OK)

`SETUP_FIRST_TIME.bat` then `START_SERVER.bat` → `http://localhost:5180`.  
Stop: `STOP_SERVER.bat`.

---

## Phase 6 — Done

- [ ] This file read first  
- [ ] OLD path asked  
- [ ] Audit shown; human confirmed  
- [ ] Approved actions applied  
- [ ] Server starts  

Later: `git pull origin main` only.
