"""Shared pytest fixtures.

`temp_db` gives each test its own throwaway SQLite file so tests never touch
(or depend on) data/customers.db, and never interfere with each other.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    # app.database imported DATABASE_PATH by value at import time, so the
    # module-level name in app.database (not app.config) is what get_conn()
    # actually reads — patch it there.
    monkeypatch.setattr("app.database.DATABASE_PATH", db_path)
    from app.database import init_schema
    init_schema()
    return db_path
