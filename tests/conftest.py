"""
Pytest fixtures for the Face Recognition AI test suite.

All tests use a dedicated test database (``data/test.db``) to avoid
touching production data. The database is reset before each test module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

# ── Ensure project root is on sys.path ────────────────────────
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ── Test database ─────────────────────────────────────────────
# Use a separate test database to avoid touching production data.
TEST_DB_DIR = Path(_project_root) / "data"
TEST_DB_DIR.mkdir(parents=True, exist_ok=True)

# Use PID-suffixed name to avoid conflicts from previous runs
_pid = os.getpid()
TEST_DB_PATH = TEST_DB_DIR / f"test_{_pid}.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# ── Monkey-patch the database module to use test DB ───────────
# This MUST happen before any service code is imported, so it's at
# module level (not inside a fixture).
import database.database as _db_mod  # noqa: E402

_db_mod.DATABASE_URL = TEST_DATABASE_URL
_db_mod.engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,  # No pooling — avoids QueuePool exhaustion during test teardown/setup
    pool_pre_ping=True,  # Verify connections are alive before using them
)
_db_mod.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_db_mod.engine,
)

# Create tables
from database.models import Base  # noqa: E402

Base.metadata.create_all(bind=_db_mod.engine)


@pytest.fixture(scope="session", autouse=True)
def _session_db() -> Iterator[None]:
    """Session-scoped DB setup (ensures tables exist once)."""
    Base.metadata.create_all(bind=_db_mod.engine)
    yield
    Base.metadata.drop_all(bind=_db_mod.engine)
    # Clean up the test database file
    try:
        if TEST_DB_PATH.exists():
            TEST_DB_PATH.unlink()
    except PermissionError:
        pass


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide a clean database session for each test.

    Uses ``rollback`` after the test so no data persists.
    """
    connection = _db_mod.engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def reset_db() -> Iterator[None]:
    """Reset all tables before each test (for tests that commit)."""
    # Dispose the pool first to release any lingering connections
    _db_mod.engine.dispose()
    Base.metadata.drop_all(bind=_db_mod.engine)
    Base.metadata.create_all(bind=_db_mod.engine)
    yield
