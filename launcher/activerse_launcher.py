#!/usr/bin/env python3
"""Thin launcher for Activerse RFID — starts START_SERVER.bat from repo root."""

import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _show_error(message: str) -> None:
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, "Activerse RFID", 0x10)
    else:
        print(message, file=sys.stderr)


def _debug(message: str) -> None:
    if os.environ.get("ACTIVERSE_LAUNCHER_DEBUG") == "1":
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "Activerse RFID (debug)", 0)
        else:
            print(message)


def main() -> int:
    root = _repo_root()
    start_bat = root / "START_SERVER.bat"

    _debug(f"Root: {root}\nSTART_SERVER.bat: {start_bat}")

    if not start_bat.is_file():
        _show_error(
            f"START_SERVER.bat not found in:\n{root}\n\n"
            "Extract the full Activerse RFID release zip to this folder."
        )
        return 1

    if sys.platform != "win32":
        _show_error("Activerse RFID launcher is for Windows only.")
        return 1

    os.startfile(str(start_bat))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
