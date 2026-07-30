import importlib
import sys

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Fresh Database backed by a scratch sqlite file, fully re-imported so
    config.DB_PATH picks up the override."""
    db_path = tmp_path / "test.sqlite"
    monkeypatch.setenv("DB_PATH", str(db_path))
    for mod in ("api.config", "api.database"):
        sys.modules.pop(mod, None)
    database_mod = importlib.import_module("api.database")
    return database_mod.Database()
