#!/usr/bin/env python3
"""
Cross-platform operator-package stager. Layout: frozen exe dir + ui/ (built
frontend) + .env.example + STOP + README. NEVER ships .py/.pyc, a real .env,
or any database (data/ is created on first run).

usage: stage_release.py <stage_dir> <frozen_dist_dir> [--windows|--macos]
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE_WIN = "Activerse RFID.exe"
STOP_BAT = f'@echo off\r\n"%~dp0{EXE_WIN}" --stop\r\n'


def main(stage: Path, dist: Path, target: str) -> int:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    # frozen runtime (exe + dlls) at the root
    shutil.copytree(dist, stage, dirs_exist_ok=True)

    # UI
    ui_src = ROOT / "frontend" / "dist"
    if not (ui_src / "index.html").is_file():
        print("ERROR: frontend/dist missing - build the frontend first")
        return 1
    shutil.copytree(ui_src, stage / "ui")

    # config template only; the real .env belongs to the venue
    shutil.copy2(ROOT / ".env.example", stage / ".env.example")

    if target == "windows":
        (stage / "STOP_SERVER.bat").write_bytes(STOP_BAT.encode("ascii"))
    else:
        shutil.copy2(ROOT / "packaging" / "STOP_SERVER.sh", stage / "STOP_SERVER.sh")
        (stage / "STOP_SERVER.sh").chmod(0o755)
    shutil.copy2(ROOT / "packaging" / "README_OPERATOR.txt", stage / "README_OPERATOR.txt")

    bad = [p for p in stage.rglob("*") if p.suffix.lower() in (".py", ".pyc", ".sqlite", ".jsx")]
    bad += [p for p in (stage / ".env", stage / "data") if p.exists()]
    if bad:
        print("ERROR: forbidden files in operator package:")
        for p in bad[:20]:
            print("  ", p)
        return 1
    print(f"staged -> {stage}")
    return 0


if __name__ == "__main__":
    tgt = "macos" if "--macos" in sys.argv else "windows"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(Path(args[0]).resolve(), Path(args[1]).resolve(), tgt))
