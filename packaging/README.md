# Operator packaging (K2b)

Binary-only Windows/macOS build of the RFID server: one Nuitka executable
(`Activerse RFID.exe`) + `ui/` (built frontend) + `.env.example`. No Python or
frontend source, no database, no real `.env` in the package.

- Windows: `powershell -File packaging\build_nuitka_windows.ps1` (CI: `.github/workflows/package.yml`)
- macOS:   `bash packaging/build_nuitka_macos.sh`
- Source-mode run (dev): `python -m floor_launcher.entry --no-browser`, stop with `python -m floor_launcher.entry --stop`
- Roles: default = supervisor (START_SERVER.bat), `--stop` (STOP_SERVER.bat), `--selftest`, `--role api` (internal)
- Layout in the install dir: `.env` (venue), `data/rfid.sqlite` (created on first start), `logs/`, `ui/`
