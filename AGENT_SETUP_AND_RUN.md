# AGENT_SETUP_AND_RUN.md — Activerse RFID (Windows reception PC)

**Audience:** an AI coding agent on **the RFID / reception Windows PC** — one-time
setup today, then daily start/stop.

**Repos:**

| Location | Role |
|----------|------|
| GitHub `main` | Going-forward **source of truth** for code |
| This PC’s **old** install (if any) | Audit once today for machine-only fixes; keep `.env` |
| `.env` on this PC | Game LAN IPs + admin password — preserve |

This repo has **no Git LFS level files**. Still audit code + any local data/assets
the old install used. Game floors handle `.led` / `.ledb` LFS on their own PCs.

Also read: `WINDOWS_ONSITE_HANDOFF.md`, `OPERATOR_GUIDE.md`,
`ONSITE_LAN_INTEGRATION_PLAN.md`.

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

## One-time sync model (today only)

```
1. Pull GitHub main into NEW folder
2. Find OLD reception install (if any)
3. AUDIT: code (and any unique assets) only on OLD → report + push to main
4. Keep .env (LAN IPs) from OLD
5. After today: git pull main only
```

Do not silently discard OLD code diffs. If reception PC has a fix GitHub lacks,
surface it and get it onto `main` before deleting OLD.

---

## Phase 0 — Prerequisites

Git, Python 3.11, Node.js LTS on PATH. (No Git LFS required here.)

---

## Phase 1 — Find OLD install

Common: `C:\activerse\activerse-rfid`, Desktop extracts. Record `OLD_ROOT`.

---

## Phase 2 — Clone GitHub `main`

```bat
mkdir C:\activerse 2>nul
cd C:\activerse
git clone https://github.com/LedVerseGameSimulators/activerse-rfid.git
cd activerse-rfid
git checkout main
git pull
```

---

## Phase 3 — ONE-TIME audit: OLD vs NEW

```powershell
$NEW = "C:\activerse\activerse-rfid"
$OLD = "C:\path\to\OLD_ROOT"
$Report = "C:\activerse\rfid-reconcile-report.txt"
$dirs = @("api","frontend\src")
$lines = @()
$lines += "NEW tip: $(git -C $NEW rev-parse --short HEAD)"
foreach ($d in $dirs) {
  $oldDir = Join-Path $OLD $d
  if (-not (Test-Path $oldDir)) { continue }
  Get-ChildItem $oldDir -Recurse -File -Include *.py,*.jsx,*.js |
    ForEach-Object {
      $rel = $_.FullName.Substring($OLD.Length).TrimStart("\")
      $counterpart = Join-Path $NEW $rel
      if (-not (Test-Path $counterpart)) {
        $lines += "ONLY_ON_MACHINE_CODE: $rel"
      } else {
        $h1 = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
        $h2 = (Get-FileHash $counterpart -Algorithm SHA256).Hash
        if ($h1 -ne $h2) { $lines += "DIFFERS_CODE: $rel" }
      }
    }
}
# Optional: Excel import templates / static assets only on machine
Get-ChildItem $OLD -Recurse -File -Include *.xlsx,*.csv,*.json -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\node_modules\\|\\data\\' } |
  ForEach-Object {
    $rel = $_.FullName.Substring($OLD.Length).TrimStart("\")
    $counterpart = Join-Path $NEW $rel
    if (-not (Test-Path $counterpart)) { $lines += "ONLY_ON_MACHINE_ASSET: $rel" }
  }
$lines | Tee-Object -FilePath $Report
```

| Finding | Action |
|---------|--------|
| Clean / only `.env` diffs | Prefer NEW; keep OLD `.env` |
| `ONLY_ON_MACHINE_CODE` / `DIFFERS_CODE` | Port into NEW → commit → **push `main`** before deleting OLD |
| `ONLY_ON_MACHINE_ASSET` | If needed for ops, add + push; else ignore |
| `.env` | Copy OLD → NEW if validated; else `.env.example` → edit |

Do **not** commit live `data\*.sqlite` or secrets.

---

## Phase 4 — Install

```bat
SETUP_FIRST_TIME.bat
```

Edit `.env`: `ADMIN_PASSWORD` + five `*_API=` LAN URLs.

---

## Phase 5 — Run

```bat
START_SERVER.bat
```

UI `http://localhost:5180` — Stop: `STOP_SERVER.bat`.

---

## Phase 6 — Done

- [ ] `main` pulled  
- [ ] One-time report cleared (no unresolved machine-only code)  
- [ ] `.env` correct  
- [ ] START / STOP work; game PCs can hit `:9000`  

Later: `git pull origin main` only.

**Note:** Level / LFS reconciliation happens on each **game** PC via that repo’s
`AGENT_SETUP_AND_RUN.md` (`.led` / `.ledb` → Git LFS). Not on this machine.
