"""
Backup — SQLite / PostgreSQL + FAISS + Metadata
================================================

Creates a complete, restorable snapshot of the system state:

    1. Database (SQLite via atomic backup API, or PostgreSQL via pg_dump)
    2. FAISS vector index   (embeddings/faiss.index)
    3. Embedding metadata   (embeddings/metadata.json)

Everything is written to ``backups/backup_YYYYMMDD_HHMMSS/`` together with
a ``manifest.json`` that records what was captured, file hashes, and database
metadata so ``scripts/restore.py`` can restore it seamlessly.

Usage:
    python scripts/backup.py
    python scripts/backup.py --output backups/custom
    python scripts/backup.py --url sqlite:///data/face_recognition.db
    python scripts/backup.py --url postgresql://user:pass@host:5432/db
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

# ── UTF-8 output (Windows consoles default to cp1252) ─────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Project root ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config.config as cfg  # noqa: E402

BACKUPS_DIR = ROOT / "backups"
EMBEDDINGS_DIR = cfg.EMBEDDINGS_DIR
FAISS_INDEX = EMBEDDINGS_DIR / "faiss.index"
METADATA = EMBEDDINGS_DIR / "metadata.json"

DEFAULT_SQLITE_PATH = ROOT / "data" / "face_recognition.db"
DEFAULT_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

# Common PostgreSQL bin locations (Windows + Linux/macOS)
PG_BIN_CANDIDATES = [
    r"C:\Program Files\PostgreSQL\17\bin",
    r"C:\Program Files\PostgreSQL\16\bin",
    r"C:\Program Files\PostgreSQL\15\bin",
    "/usr/lib/postgresql/17/bin",
    "/usr/lib/postgresql/16/bin",
    "/usr/local/bin",
    "/usr/bin",
]


def is_sqlite_url(url: str) -> bool:
    """Return True if URL represents an SQLite database."""
    return url.lower().startswith("sqlite:") or not ("://" in url and not url.lower().startswith("sqlite:"))


def extract_sqlite_path(url: str) -> Path:
    """Extract SQLite filesystem Path from a sqlite:/// URL or plain path."""
    if url.lower().startswith("sqlite:///"):
        path_str = url[10:]
        return Path(path_str)
    elif url.lower().startswith("sqlite://"):
        path_str = url[9:]
        return Path(path_str)
    return Path(url)


def find_pg_bin() -> Path:
    """Locate the PostgreSQL bin directory (for pg_dump / psql)."""
    found = shutil.which("pg_dump")
    if found:
        return Path(found).parent
    for cand in PG_BIN_CANDIDATES:
        if (Path(cand) / "pg_dump.exe").exists() or (Path(cand) / "pg_dump").exists():
            return Path(cand)
    raise FileNotFoundError("pg_dump not found. Install PostgreSQL or add its bin directory to PATH.")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_credentials(url: str) -> tuple[str, str, str, str, str]:
    """Return (host, port, user, password, dbname) from a postgres URL."""
    parsed = urlparse(url)
    return (
        parsed.hostname or "localhost",
        str(parsed.port or 5432),
        parsed.username or "postgres",
        unquote(parsed.password or ""),
        parsed.path.lstrip("/") or "postgres",
    )


def preflight_check_postgres(url: str) -> None:
    """Verify PostgreSQL is reachable before dumping."""
    import psycopg2

    host, port, user, password, dbname = extract_credentials(url)
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=dbname,
        connect_timeout=5,
    )
    conn.close()


def backup_sqlite(db_file: Path, backup_dir: Path) -> tuple[Path, str]:
    """Atomically snapshot SQLite database using SQLite backup API."""
    if not db_file.exists():
        raise FileNotFoundError(f"SQLite database file not found at: {db_file}")

    dump_path = backup_dir / "database.sqlite"
    print(f"\n[1/3] Dumping SQLite database ({db_file.name})...")

    # Connect to source and force WAL checkpoint to guarantee zero uncommitted writes
    src_conn = sqlite3.connect(str(db_file), timeout=10.0)
    try:
        src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    except Exception as exc:
        print(f"  i WAL checkpoint note: {exc}")

    dest_conn = sqlite3.connect(str(dump_path))
    try:
        src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    print(f"  + SQLite snapshot: {dump_path.name} ({dump_path.stat().st_size:,} bytes)")
    return dump_path, "sqlite"


def backup_postgres(url: str, backup_dir: Path) -> tuple[Path, str]:
    """Dump PostgreSQL database using pg_dump."""
    host, port, user, password, dbname = extract_credentials(url)
    if not re.fullmatch(r"[A-Za-z0-9_]+", dbname):
        raise ValueError(f"Invalid database name: {dbname!r}")

    pg_bin = find_pg_bin()
    print("  PostgreSQL : {}:{}".format(host, port))
    preflight_check_postgres(url)

    dump_path = backup_dir / f"{dbname}.sql"
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    cmd = [
        str(pg_bin / "pg_dump"),
        "-h",
        host,
        "-p",
        port,
        "-U",
        user,
        "--no-owner",
        "--no-privileges",
        "-f",
        str(dump_path),
        dbname,
    ]
    print("\n[1/3] Dumping PostgreSQL...")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed:\n{result.stderr[-2000:]}")
    print(f"  + SQL dump: {dump_path.name} ({dump_path.stat().st_size:,} bytes)")
    return dump_path, "postgres"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup SQLite/PostgreSQL + FAISS + metadata")
    parser.add_argument(
        "--output", default=str(BACKUPS_DIR), help="Base output directory (default: backups/)"
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Database URL or SQLite path to dump")
    args = parser.parse_args()

    url = args.url
    print("=" * 64)
    print("  Face Recognition AI — System Backup")
    print("=" * 64)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(args.output) / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Backup dir : {backup_dir}")

    try:
        # ── 1. Database dump ─────────────────────────────────
        if is_sqlite_url(url):
            sqlite_path = extract_sqlite_path(url)
            dump_path, db_type = backup_sqlite(sqlite_path, backup_dir)
            url_redacted = f"sqlite:///{sqlite_path.name}"
        else:
            dump_path, db_type = backup_postgres(url, backup_dir)
            host, port, user, _, dbname = extract_credentials(url)
            url_redacted = f"postgresql://{user}:***@{host}:{port}/{dbname}"

        # ── 2. FAISS index + metadata ─────────────────────────
        artifacts = {}
        print("\n[2/3] Copying FAISS index + metadata...")
        for name, src in [("faiss.index", FAISS_INDEX), ("metadata.json", METADATA)]:
            if src.exists():
                dst = backup_dir / name
                shutil.copy2(src, dst)
                artifacts[name] = {
                    "size": src.stat().st_size,
                    "sha256": sha256(src),
                    "original_path": str(src),
                }
                print(f"  + {name}: {src.stat().st_size:,} bytes")
            else:
                artifacts[name] = {"exists": False, "original_path": str(src)}
                print(f"  . {name}: not present (fresh installation?)")

        # ── 3. Manifest ───────────────────────────────────────
        print("\n[3/3] Writing manifest...")
        manifest = {
            "created_at": datetime.datetime.now().isoformat(),
            "tool_version": "backup.py-v2.1",
            "database": {
                "type": db_type,
                "url_redacted": url_redacted,
                "dump_file": dump_path.name,
                "dump_size": dump_path.stat().st_size,
                "dump_sha256": sha256(dump_path),
            },
            "artifacts": artifacts,
        }
        manifest_path = backup_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"  + {manifest_path.name}")

        print("\n" + "=" * 64)
        print(f"  Backup complete: {backup_dir}")
        print(f"  Restore with: python scripts/restore.py --backup-dir {backup_dir.name}")
        print("=" * 64)
        return 0
    except Exception as exc:
        shutil.rmtree(backup_dir, ignore_errors=True)
        print(f"  x Backup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
