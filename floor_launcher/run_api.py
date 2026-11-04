"""API role: same as `python -m api.main` in START_SERVER.bat (uvicorn, API_HOST:API_PORT)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    from api.runtime_paths import data_dir, install_root, load_env_file, logs_dir

    ir = install_root()
    # The bat ran the API with cwd = repo root; keep that.
    os.chdir(str(ir))
    data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    if str(ir) not in sys.path:
        sys.path.insert(0, str(ir))

    # .env must be in the environment BEFORE api.config is imported.
    # Real environment variables win (override=False).
    loaded = load_env_file()

    from .product import API_PORT

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", str(API_PORT)))

    import uvicorn
    from api.main import app
    from api.config import DB_PATH

    print(f"[api] root={ir} env_loaded={loaded} db={DB_PATH}", flush=True)
    print(f"[api] listening on {host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info", loop="asyncio", http="h11", ws="none")


if __name__ == "__main__":
    main()
