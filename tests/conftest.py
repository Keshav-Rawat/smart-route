"""
SmartRoute — Test Configuration & Fixtures
===========================================
Shared pytest fixtures for the entire test suite.

Run all tests:
  pytest tests/ -v

Run a single file:
  pytest tests/test_backend.py -v
"""

import sys
import os
import tempfile
import pytest

# ── Add source modules to sys.path ────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "simulation"))
sys.path.insert(0, os.path.join(ROOT, "forecasting"))


@pytest.fixture(scope="session", autouse=True)
def temp_database(tmp_path_factory):
    """
    Replace the production SQLite DB with a fresh temp DB for the test
    session. Automatically torn down when all tests finish.
    """
    db_file = str(tmp_path_factory.mktemp("db") / "test_smartroute.db")
    os.environ["SMARTROUTE_DB"] = db_file

    # Patch the module-level variable before any test imports database
    import database as db_module
    db_module.DB_PATH = db_file
    db_module.init_db()

    yield db_file

    # Cleanup
    if os.path.exists(db_file):
        os.remove(db_file)
