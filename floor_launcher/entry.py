"""
Single entry point for the packaged server (one exe, several roles):

  Activerse RFID.exe              start everything (what START_SERVER.bat did)
  Activerse RFID.exe --stop       what STOP_SERVER.bat did
  Activerse RFID.exe --selftest   read-only health report
  Activerse RFID.exe --role api   internal: spawned by the supervisor
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main(argv=None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)

    if "--role" in argv:
        role = argv[argv.index("--role") + 1]
        if role == "api":
            from floor_launcher import run_api

            run_api.main()
        else:
            sys.exit(f"unknown role: {role}")
        return

    if "--selftest" in argv:
        from floor_launcher import selftest

        sys.exit(selftest.run())

    if "--stop" in argv:
        from floor_launcher import procs

        procs.stop_all()
        print("Stopped.")
        return

    from floor_launcher import supervisor

    supervisor.main(argv)


if __name__ == "__main__":
    main()
