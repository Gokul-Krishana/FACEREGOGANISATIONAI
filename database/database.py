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

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, TypeVar

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

import config.config as cfg
from database.models import Base

logger = logging.getLogger(__name__)

_F = TypeVar("_F", bound=Callable[..., Any])

# ── Database URL ──────────────────────────────────────────────
# In production, this will be loaded from environment variables (PostgreSQL).
# In development, it falls back to SQLite.

DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()

if DB_TYPE == "postgres":
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set for PostgreSQL mode")
    connect_args = {}
    # Connection-pool tuning for production. Values are configurable via
    # environment variables (see .env.example). ``pool_pre_ping`` validates
    # checked-out connections so stale sockets after a DB restart are
    # transparently recycled instead of surfacing as application errors.
    _engine_kwargs: dict = {
        "pool_pre_ping": os.getenv("DB_POOL_PRE_PING", "true").lower() in ("1", "true", "yes", "on"),
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_POOL_MAX_OVERFLOW", "10")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
    }
else:
    DB_DIR = cfg.ROOT_DIR / "data"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH = DB_DIR / "face_recognition.db"
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    connect_args = {"check_same_thread": False}
    _engine_kwargs = {"pool_pre_ping": True}

engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True to see all SQL queries
    connect_args=connect_args,
    **_engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Public API ────────────────────────────────────────────────


def retry_on_transient(max_attempts: int = 3, base_delay: float = 0.5) -> Callable[[_F], _F]:
    """Retry a callable on transient database failures.

    Only ``OperationalError`` (connection refused, server closed the
    connection, lock timeout) is retried — programmer errors and data
    errors propagate immediately. Small exponential backoff between
    attempts keeps a DB restart from failing the whole application.
    """

    def decorator(fn: _F) -> _F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[OperationalError] = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except OperationalError as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        break
                    delay = base_delay * attempt
                    logger.warning(
                        "Transient database failure on %s (attempt %d/%d); retrying in %.1fs",
                        getattr(fn, "__name__", "db_operation"),
                        attempt,
                        max_attempts,
                        delay,
                    )
                    time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


@retry_on_transient()
def run_migrations() -> None:
    """Apply all pending Alembic migrations.

    Uses the ``alembic.ini`` at the project root.  This is the
    recommended way to manage schema changes in production.

    Retried automatically on transient connection failures so a
    database that is still starting up does not fail the boot.
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

    Transient connection failures (e.g. database restarting) are retried
    with a short backoff before giving up.

    Usage::

        with get_session() as session:
            employees = session.query(Employee).all()
    """
    db: Optional[Session] = None
    last_exc: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            db = SessionLocal()
            break
        except OperationalError as exc:
            last_exc = exc
            if attempt < 3:
                logger.warning(
                    "Transient failure creating DB session (attempt %d/3); retrying",
                    attempt,
                )
                time.sleep(0.5 * attempt)
    if db is None:
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("Failed to create database session")
    try:
        yield db
    finally:
        db.close()


def reset_db() -> None:
    """Drop all tables and recreate them (for testing)."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
