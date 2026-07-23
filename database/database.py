"""
Database connection and session management.

Uses SQLAlchemy 2.0 with SQLite as the backend. The connection URL
can be configured via ``config/settings.yaml``.

Schema Migrations
-----------------
This project uses **Alembic** for database migrations.  After changing
``database/models.py``, run::

    alembic revision --autogenerate -m "description of change"
    alembic upgrade head

To apply all pending migrations::

    alembic upgrade head

To undo the last migration::

    alembic downgrade -1

Usage::

    from database.database import get_session, init_db

    # First-time setup (creates tables if they don't exist)
    init_db()

    # Get a session
    with get_session() as session:
        employee = session.query(Employee).first()
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import config.config as cfg
from database.models import Base

# ── Database URL ──────────────────────────────────────────────
# Default: SQLite at <project_root>/data/face_recognition.db
DB_DIR = cfg.ROOT_DIR / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "face_recognition.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    echo=False,               # Set to True to see all SQL queries
    connect_args={"check_same_thread": False},  # Needed for Streamlit multi-threading
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Public API ────────────────────────────────────────────────


def run_migrations() -> None:
    """Apply all pending Alembic migrations.

    Uses the ``alembic.ini`` at the project root.  This is the
    recommended way to manage schema changes in production.
    """
    alembic_cfg = AlembicConfig(cfg.ROOT_DIR / "alembic.ini")
    alembic_command.upgrade(alembic_cfg, "head")


def init_db() -> None:
    """Ensure database schema is up to date.

    Priority order:
    1. Try Alembic migrations (if alembic.ini exists)
    2. Fall back to ``Base.metadata.create_all()`` for fresh databases

    ``create_all()`` is idempotent — it skips tables that already exist.
    After a fallback, Alembic is stamped to ``head`` so the version
    table stays in sync.
    """
    alembic_ini = cfg.ROOT_DIR / "alembic.ini"
    if alembic_ini.exists():
        try:
            run_migrations()
            return
        except Exception as exc:
            logging.warning(
                "Alembic migration failed (%s); falling back to create_all(). "
                "Run `alembic stamp head` if this is unexpected.",
                exc,
            )

    Base.metadata.create_all(bind=engine)

    # Stamp the DB so Alembic knows this revision is applied
    try:
        alembic_cfg = AlembicConfig(alembic_ini)
        alembic_command.stamp(alembic_cfg, "head")
    except Exception:
        pass  # Non-critical; alembic will catch up on next upgrade


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a database session (context manager).

    Usage::

        with get_session() as session:
            employees = session.query(Employee).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db() -> None:
    """Drop all tables and recreate them (for testing)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
