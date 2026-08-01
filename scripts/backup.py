"""
Backup — PostgreSQL + FAISS + Metadata
========================================

Creates a complete, restorable snapshot of the system state:

    1. PostgreSQL database  (pg_dump → plain SQL)
    2. FAISS vector index   (embeddings/faiss.index)
    3. Embedding metadata   (embeddings/metadata.json)

Everything is written to ``backups/backup_YYYYMMDD_HHMMSS/`` together with
a ``manifest.json`` that records what was captured, file hashes, and the
original ``DATABASE_URL`` (password redacted) so ``scripts/restore.py`` can
restore it.

Usage:
    python scripts/backup.py
    python scripts/backup.py --output backups/custom
    python scripts/backup.py --url postgresql://user:pass@host:5432/db

Requires:
    - pg_dump on PATH or installed PostgreSQL (auto-detected on Windows)
    - psycopg2 for the pre-flight connection check
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
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

import config.config as cfg

BACKUPS_DIR = ROOT / "backups"
EMBEDDINGS_DIR = cfg.EMBEDDINGS_DIR
FAISS_INDEX = EMBEDDINGS_DIR / "faiss.index"
METADATA = EMBEDDINGS_DIR / "metadata.json"

DEFAULT_URL = os.getenv("DATABASE_URL", "postgresql://faceai:changeme@localhost:5432/face_recognition")

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


def find_pg_bin() -> Path:
    """Locate the PostgreSQL bin directory (for pg_dump / psql)."""
    found = shutil.which("pg_dump")
    if found:
        return Path(found).parent
    for cand in PG_BIN_CANDIDATES:
        if (Path(cand) / "pg_dump.exe").exists() or (Path(cand) / "pg_dump").exists():
            return Path(cand)
    raise FileNotFoundError(
        "pg_dump not found. Install PostgreSQL or add its bin directory to PATH."
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_credentials(url: str) -> tuple[str, str, str, str, str]:
    """Return (host, port, user, password, dbname) from a postgres URL.

    The password is URL-decoded (``urlparse`` returns the encoded form,
    which would break credentials containing ``%``, ``@``, etc.).
    """
    parsed = urlparse(url)
    return (
        parsed.hostname or "localhost",
        str(parsed.port or 5432),
        parsed.username or "postgres",
        unquote(parsed.password or ""),
        parsed.path.lstrip("/") or "postgres",
    )


def preflight_check(url: str) -> None:
    """Verify PostgreSQL is reachable before dumping."""
    import psycopg2
    host, port, user, password, dbname = extract_credentials(url)
    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname,
        connect_timeout=5,
    )
    conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup PostgreSQL + FAISS + metadata")
    parser.add_argument("--output", default=str(BACKUPS_DIR),
                        help="Base output directory (default: backups/)")
    parser.add_argument("--url", default=DEFAULT_URL,
                        help="PostgreSQL URL to dump")
    args = parser.parse_args()

    url = args.url
    host, port, user, password, dbname = extract_credentials(url)
    if not re.fullmatch(r"[A-Za-z0-9_]+", dbname):
        print(f"x Invalid database name: {dbname!r}")
        return 1
    try:
        pg_bin = find_pg_bin()
    except FileNotFoundError as exc:
        print(f"x {exc}")
        return 1

    print("=" * 64)
    print("  System Backup")
    print("=" * 64)
    print(f"  PostgreSQL : {host}:{port}/{dbname}")
    print(f"  pg_dump    : {pg_bin / 'pg_dump'}")

    # Pre-flight check
    try:
        preflight_check(url)
        print("  Connection : OK")
    except Exception as exc:
        print(f"  x Cannot reach PostgreSQL: {exc}")
        return 1

    # Create backup folder
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(args.output) / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Backup dir : {backup_dir}")

    try:
        # ── 1. PostgreSQL dump ─────────────────────────────────
        dump_path = backup_dir / f"{dbname}.sql"
        env = dict(os.environ)
        if password:
            env["PGPASSWORD"] = password
        cmd = [
            str(pg_bin / "pg_dump"),
            "-h", host, "-p", port, "-U", user,
            "--no-owner", "--no-privileges",
            "-f", str(dump_path), dbname,
        ]
        print("\n[1/3] Dumping PostgreSQL...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  x pg_dump failed:\n{result.stderr[-2000:]}")
            shutil.rmtree(backup_dir, ignore_errors=True)
            return 1
        print(f"  + SQL dump: {dump_path.name} ({dump_path.stat().st_size:,} bytes)")

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
            "tool_version": "backup.py",
            "database": {
                "url_redacted": f"postgresql://{user}:***@{host}:{port}/{dbname}",
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
        print("  Restore with: python scripts/restore.py --backup-dir "
              f"{backup_dir.name} --url postgresql://{user}:***@{host}:{port}/{dbname}")
        print("=" * 64)
        return 0
    except Exception:
        # Don't leave a broken/partial backup directory behind
        shutil.rmtree(backup_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
