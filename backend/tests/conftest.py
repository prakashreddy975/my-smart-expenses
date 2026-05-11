import sys

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Isolated SQLite DB per test; avoids touching developer expense_tracker.db."""
    db_path = tmp_path / "test_expense_tracker.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("EXPENSE_TRACKER_DB", str(db_path))
    monkeypatch.setenv("DISABLE_CSV_IMPORT", "1")
    for mod in ("app", "database"):
        sys.modules.pop(mod, None)
    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()
