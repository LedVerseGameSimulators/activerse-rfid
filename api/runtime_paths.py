"""
Install-root / resource path helpers for frozen (Nuitka) and source runs.

Source: install root = repo root (parent of api/), exactly what the .bat stack used.
Frozen: install root = the directory holding the exe; ui/, data/, logs/ and .env
live next to it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True under PyInstaller (sys.frozen) or Nuitka (__compiled__)."""
    if getattr(sys, "frozen", False):
        return True
    return bool(globals().get("__compiled__"))


def self_exe() -> list:
    """Command that re-launches this program (used to spawn role processes)."""
    if is_frozen():
        argv0 = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
        if argv0 is not None and argv0.is_file() and argv0.suffix.lower() != ".py":
            return [str(argv0)]
        return [sys.executable]
    entry = Path(__file__).resolve().parent.parent / "floor_launcher" / "entry.py"
    return [sys.executable, str(entry)]


def _frozen_exe_dir() -> Path:
    argv0 = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    if argv0 is not None and argv0.is_file() and argv0.suffix.lower() != ".py":
        return argv0.parent
    return Path(sys.executable).resolve().parent


def install_root() -> Path:
    """Directory that contains ui/, data/, logs/, .env (honors ACTIVERSE_ROOT)."""
    env = os.getenv("ACTIVERSE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    if is_frozen():
        return _frozen_exe_dir()
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return install_root() / "data"


def logs_dir() -> Path:
    return install_root() / "logs"


def env_file() -> Path:
    """The operator .env (honors ENV_FILE)."""
    env = os.getenv("ENV_FILE")
    if env:
        return Path(env).expanduser().resolve()
    return install_root() / ".env"


def ui_dir() -> Path:
    """
    Built frontend. Frozen: install_root()/ui. Source: frontend/dist.
    Honors UI_DIR env.
    """
    env = os.getenv("UI_DIR")
    if env:
        return Path(env).expanduser().resolve()
    if is_frozen():
        return install_root() / "ui"
    return install_root() / "frontend" / "dist"


def resolve_db_path(value: str | None) -> str:
    """DB_PATH: absolute as given; relative -> against the install root
    (the .bat ran with cwd = repo root, so ./data/rfid.sqlite meant the same)."""
    if not value:
        return str(data_dir() / "rfid.sqlite")
    p = Path(value).expanduser()
    return str(p if p.is_absolute() else install_root() / p)


def load_env_file() -> bool:
    """Load .env (python-dotenv) without overriding real environment variables."""
    f = env_file()
    if not f.is_file():
        return False
    from dotenv import load_dotenv

    load_dotenv(f, override=False)
    return True
