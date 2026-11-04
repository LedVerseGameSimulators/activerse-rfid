"""
RFID supervisor — what START_SERVER.bat does, as one program.

  1. .env must exist (created from .env.example, then stop and tell the tech to edit it)
  2. data/ exists
  3. stop any previous run (STOP /quiet)
  4. start the API (:9000, same as `python -m api.main`)
  5. wait for the UI (now served by the API itself) and /health
  6. open the isolated kiosk browser + Ctrl+Shift+K exit hotkey (ACTIVERSE_KIOSK=0 -> normal browser)
  7. stay alive; if the API dies, stop everything and say so
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import List

from api.runtime_paths import env_file, install_root, self_exe

from . import kiosk, procs
from .product import API_PORT, DISPLAY_NAME, SLUG

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} [supervisor] {msg}"
    try:
        print(line, flush=True)
    except (OSError, ValueError):
        pass
    try:
        with open(procs.logs_dir() / "supervisor.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def fail(msg: str, code: int = 1) -> None:
    """Log, and on Windows tell the operator (console is hidden)."""
    _log(f"ERROR: {msg}")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg + "\n\nSee the logs folder.", DISPLAY_NAME, 0x10)
        except Exception:
            pass
    sys.exit(code)


def hide_console() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _get(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.status, resp.read()


def _wait(path: str, tries: int = 30) -> bool:
    for _ in range(tries):
        try:
            status, _ = _get(f"http://127.0.0.1:{API_PORT}{path}")
            if status == 200:
                return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(2)
    return False


def _spawn_api(env: dict, root: Path) -> subprocess.Popen:
    out = open(procs.logs_dir() / "api.console.log", "ab")
    return subprocess.Popen(
        self_exe() + ["--role", "api"],
        env=env,
        cwd=str(root),
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )


def _ensure_env_file(root: Path) -> None:
    """START_SERVER.bat: no .env -> copy .env.example and stop so the tech can edit it."""
    ef = env_file()
    if ef.is_file():
        return
    example = root / ".env.example"
    if example.is_file():
        shutil.copyfile(example, ef)
        fail(
            f"Created {ef.name} from .env.example.\n\n"
            "IMPORTANT: Edit .env and set the five game PC IPs + ADMIN_PASSWORD.\n"
            "Then start Activerse RFID again."
        )
    fail(".env is missing. Ask tech to create it from .env.example.")


def main(argv: List[str]) -> None:
    kiosk_on = os.environ.get("ACTIVERSE_KIOSK", "1") != "0"
    no_browser = "--no-browser" in argv  # CI / headless smoke tests
    if "--console" not in argv and os.environ.get("ACTIVERSE_CONSOLE") != "1":
        hide_console()

    root = install_root()
    os.chdir(str(root))
    (root / "data").mkdir(exist_ok=True)
    _log(f"{DISPLAY_NAME} starting — install_root={root}")

    _ensure_env_file(root)

    _log("stopping any previous run")
    procs.stop_all()
    time.sleep(2)

    env = os.environ.copy()
    api = _spawn_api(env, root)
    children = [api]
    procs.write_pids([os.getpid()] + [p.pid for p in children])
    _log(f"API pid={api.pid} :{API_PORT}")

    def _stop_and_exit(code: int = 0) -> None:
        for p in children:
            if p.poll() is None:
                procs.kill_tree(p.pid)
        kiosk.kill_kiosk(SLUG)
        procs.free_ports()
        sys.exit(code)

    if not _wait("/"):
        _log("WARNING: UI did not respond yet. Opening browser anyway.")
    else:
        _log("RFID UI is ready.")
    if not _wait("/health", tries=1):
        _log("WARNING: /health not confirmed yet. Check logs/api.console.log.")

    listener = None
    if kiosk_on and not no_browser:
        listener = kiosk.HotkeyListener(SLUG)
        listener.start()
        listener.registered.wait(2)
    if not no_browser:
        try:
            kiosk.launch(f"http://127.0.0.1:{API_PORT}/", SLUG, kiosk=kiosk_on)
        except RuntimeError as exc:
            # open-ui.bat's failure did not abort START_SERVER.bat: server keeps running.
            _log(f"WARNING: could not open browser: {exc}")

    _log(f"{DISPLAY_NAME} is running at http://127.0.0.1:{API_PORT}/. Ctrl+Shift+K exits kiosk. STOP to quit.")
    while True:
        for p in children:
            code = p.poll()
            if code is not None:
                _log(f"child pid={p.pid} exited code={code}; stopping everything")
                _stop_and_exit(1)
        time.sleep(1)
