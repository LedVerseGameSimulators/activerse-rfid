"""
`Activerse RFID.exe --selftest` — one pass/fail report to send back from the RFID PC.

Read-only: never creates/migrates the DB, never starts anything.
"""
from __future__ import annotations

import os
import socket
import sqlite3
from typing import List, Tuple

from api.runtime_paths import data_dir, env_file, install_root, is_frozen, resolve_db_path, ui_dir

from . import kiosk
from .product import API_PORT, DISPLAY_NAME

Result = Tuple[str, bool, str]


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def run() -> int:
    out: List[Result] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        out.append((name, ok, detail))

    ir = install_root()
    check("build type", True, f"frozen={is_frozen()} install_root={ir}")
    check("UI present", (ui_dir() / "index.html").is_file(), str(ui_dir()))
    ef, ex = env_file(), ir / ".env.example"
    check(".env present or .env.example", ef.is_file() or ex.is_file(), f"{'.env' if ef.is_file() else '.env.example'} in {ir}")

    dd = data_dir()
    probe_dir = dd if dd.is_dir() else ir
    probe = probe_dir / ".selftest-write"
    try:
        probe.write_text("x")
        probe.unlink()
        check("data dir writable", True, str(probe_dir) + ("" if dd.is_dir() else " (data/ is created on first start)"))
    except OSError as exc:
        check("data dir writable", False, f"{probe_dir}: {exc}")

    dbp = os.getenv("DB_PATH")
    dbp = resolve_db_path(dbp)
    try:
        con = sqlite3.connect(":memory:")
        con.execute("select 1")
        con.close()
        check("sqlite opens", True, f"sqlite {sqlite3.sqlite_version}; db={dbp} ({'exists' if os.path.isfile(dbp) else 'will be created'})")
    except Exception as exc:
        check("sqlite opens", False, repr(exc))

    for name, mod in (("uvicorn", "uvicorn"), ("fastapi", "fastapi"), ("httpx", "httpx"),
                      ("loguru", "loguru"), ("dotenv", "dotenv"), ("openpyxl", "openpyxl"),
                      ("multipart", "multipart")):
        try:
            __import__(mod)
            check(f"import {name}", True)
        except Exception as exc:
            check(f"import {name}", False, repr(exc))
    try:
        import api.main  # noqa: F401  (routes + models import cleanly)
        check("import api.main", True)
    except Exception as exc:
        check("import api.main", False, repr(exc))

    check("browser (Chrome/Edge)", bool(kiosk.find_browser()), str(kiosk.find_browser()))
    free = _port_free(API_PORT)
    check(f"API port {API_PORT} free", free, "" if free else "in use (server already running?)")

    width = max(len(n) for n, _, _ in out)
    print(f"\n{DISPLAY_NAME} self-test\n" + "-" * 60)
    for name, ok, detail in out:
        print(f"{'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail}")
    failed = [n for n, ok, _ in out if not ok]
    print("-" * 60 + f"\n{'ALL PASS' if not failed else 'FAILED: ' + ', '.join(failed)}\n")
    return 0 if not failed else 1
