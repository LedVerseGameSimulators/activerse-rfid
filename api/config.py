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
# Keys MUST equal each game's own GAME_NAME so central_scores.game aligns with
# the game-side rows. Ports are the confirmed real ports (verified from each
# repo's ws_bridge.py / vite.config.js / config.js).
GAME_REGISTRY = {
    "hoops":   {"api": os.getenv("HOOPS_API",   "http://localhost:8000"), "label": "Hoops"},
    "laser":   {"api": os.getenv("LASER_API",   "http://localhost:8001"), "label": "Laser Trap"},
    "climb":   {"api": os.getenv("CLIMB_API",   "http://localhost:8002"), "label": "Climb"},
    "grid":    {"api": os.getenv("GRID_API",    "http://localhost:8003"), "label": "Floor Is Lava"},
    "led_hex": {"api": os.getenv("LED_HEX_API", "http://localhost:8004"), "label": "LED Hexagon"},
}

# ── Poller ─────────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "120"))  # 2 min

# ── API ────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "9000"))
