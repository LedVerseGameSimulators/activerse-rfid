# Activerse RFID launcher

Build the operator `Activerse RFID.exe` on Windows with PyInstaller:

```bat
pip install pyinstaller
pyinstaller launcher/Activerse_RFID.spec --noconfirm
```

The executable is written to `dist/Activerse RFID.exe`. Place it next to `START_SERVER.bat` in the release folder (or use the GitHub Actions `Package Windows` workflow on a `v*` tag).
