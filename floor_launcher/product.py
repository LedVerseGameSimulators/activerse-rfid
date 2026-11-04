"""Per-product constants. This is the only file that differs between product repos."""

SLUG = "rfid"             # kiosk profile slug (ActiverseKiosk\rfid), release/zip names
DISPLAY_NAME = "Activerse RFID"
API_PORT = 9000           # UI is served by the API on the same port
# Ports freed on STOP: same set STOP_SERVER.bat freed (9000 API, 5180 legacy vite preview).
STOP_PORTS = (9000, 5180)
