"""
RFID Server Configuration
Central hub for all 4 game machines.
"""
import os
from pathlib import Path

# ── Database ───────────────────────────────────────────────────────────────
# Dev: SQLite (same machine). Prod: MySQL on this server.
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "rfid.sqlite"))

# ── Session rules ──────────────────────────────────────────────────────────
DEFAULT_SESSION_MINUTES = int(os.getenv("DEFAULT_SESSION_MINUTES", "60"))
MIN_MINUTES_TO_START    = int(os.getenv("MIN_MINUTES_TO_START", "5"))

# ── Game registry ──────────────────────────────────────────────────────────
# In prod, change to actual LAN IPs per machine.
GAME_REGISTRY = {
    "hoops":   {"api": os.getenv("HOOPS_API",   "http://localhost:8000"), "label": "Hoops"},
    "climb":   {"api": os.getenv("CLIMB_API",   "http://localhost:8001"), "label": "Climb"},
    "led_hex": {"api": os.getenv("LED_HEX_API", "http://localhost:8002"), "label": "LED Hex"},
    "laser":   {"api": os.getenv("LASER_API",   "http://localhost:8003"), "label": "Laser Trap"},
}

# ── Poller ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))  # 2 min

# ── API ────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "9000"))
