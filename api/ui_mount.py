"""
Serve the built admin/leaderboard UI from the API itself (replaces the Node
`vite preview` server on :5180).

Route precedence reproduces what the Vite proxy gave:
  /api/*  -> the API, prefix stripped (vite.config.js: rewrite ^/api -> '')
  other   -> the UI (SPA: browser navigations get index.html)
Callers that are not browsers (games, httpx: Accept */*) keep hitting the plain
API paths (/validate, /players, ...) untouched.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

# Paths a browser may open directly that must stay API (docs/health), not the SPA.
_API_ONLY = ("/health", "/docs", "/redoc", "/openapi.json", "/internal")


class _UiRouting:
    """Pure ASGI middleware: /api prefix strip + SPA fallback for navigations."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            if path == "/api" or path.startswith("/api/"):
                path = path[4:] or "/"
                scope = dict(scope, path=path, raw_path=path.encode())
            elif scope["method"] == "GET" and not path.startswith(_API_ONLY):
                last = path.rsplit("/", 1)[-1]
                if "." not in last and path != "/":
                    accept = b""
                    for k, v in scope["headers"]:
                        if k == b"accept":
                            accept = v
                            break
                    if b"text/html" in accept:
                        scope = dict(scope, path="/index.html", raw_path=b"/index.html")
        await self.app(scope, receive, send)


def mount_ui(app: FastAPI, ui_path: Path) -> bool:
    if not (ui_path.is_dir() and (ui_path / "index.html").is_file()):
        logger.warning(f"UI not mounted (missing {ui_path / 'index.html'}); API only")
        return False
    app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="ui")
    app.add_middleware(_UiRouting)
    logger.info(f"Serving UI from {ui_path} (same origin; /api/* aliases the API)")
    return True
