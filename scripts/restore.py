"""
Restore — SQLite / PostgreSQL + FAISS + Metadata
=================================================

Restores a snapshot created by ``scripts/backup.py``:

    1. Database (SQLite atomic restoration or PostgreSQL via psql)
    2. FAISS vector index   (embeddings/faiss.index)
    3. Embedding metadata   (embeddings/metadata.json)

Usage:
    python scripts/restore.py --backup-dir backups/backup_20260731_120000
    python scripts/restore.py --backup-dir <dir> --url postgresql://user:pass@host:5432/db
    python scripts/restore.py --backup-dir <dir> --dry-run
"""

from __future__ import annotations

import argparse
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

EMBEDDINGS_DIR = cfg.EMBEDDINGS_DIR
DEFAULT_SQLITE_PATH = ROOT / "data" / "face_recognition.db"

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
    """Locate the PostgreSQL bin directory (for psql)."""
    found = shutil.which("psql")
    if found:
        return Path(found).parent
    for cand in PG_BIN_CANDIDATES:
        if (Path(cand) / "psql.exe").exists() or (Path(cand) / "psql").exists():
            return Path(cand)
    raise FileNotFoundError("psql not found. Install PostgreSQL or add its bin directory to PATH.")


def extract_credentials(url: str) -> tuple[str, str, str, str, str]:
    parsed = urlparse(url)
    return (
        parsed.hostname or "localhost",
        str(parsed.port or 5432),
        parsed.username or "postgres",
        unquote(parsed.password or ""),
        parsed.path.lstrip("/") or "postgres",
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_artifacts(backup_dir: Path, manifest: dict) -> bool:
    """Verify stored files match the manifest hashes. Returns True if OK."""
    ok = True
    db_info = manifest.get("database", {})
    dump_file = db_info.get("dump_file")
    expected_hash = db_info.get("dump_sha256")
    if dump_file and expected_hash:
        dump_path = backup_dir / dump_file
        if dump_path.exists():
            actual = sha256(dump_path)
            if actual != expected_hash:
                print(f"  x Hash MISMATCH for {dump_file}")
                ok = False
            else:
                print(f"  + {dump_file}: hash verified")
        else:
            print(f"  x {dump_file} missing")
            ok = False

    for name in ("faiss.index", "metadata.json"):
        art = manifest.get("artifacts", {}).get(name, {})
        exp = art.get("sha256")
        if not exp:
            continue
        src = backup_dir / name
        if src.exists():
            actual = sha256(src)
            if actual != exp:
                print(f"  x Hash MISMATCH for {name}")
                ok = False
            else:
                print(f"  + {name}: hash verified")
    return ok


def restore_sqlite_db(dump_path: Path, target_path: Path, dry_run: bool = False) -> None:
    """Restore SQLite database file atomically with integrity verification."""
    print(f"  Target DB   : {target_path}")
    print(f"  Dump file   : {dump_path.name}")

    if dry_run:
        print("  [dry-run] Would replace target SQLite DB and verify integrity.")
        return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Pre-backup existing DB if present
    if target_path.exists():
        backup_curr = target_path.with_suffix(".pre_restore")
        shutil.copy2(target_path, backup_curr)
        print(f"  i Created pre-restore backup: {backup_curr.name}")

    # Copy dump into place
    shutil.copy2(dump_path, target_path)

    # Verify SQLite integrity
    conn = sqlite3.connect(str(target_path))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchone()[0]
        if res != "ok":
            raise RuntimeError(f"Restored SQLite DB failed integrity check: {res}")
        print(f"  + SQLite integrity check: {res}")
    finally:
        conn.close()


def restore_postgres_db(dump_path: Path, url: str, dry_run: bool = False) -> None:
    """Restore PostgreSQL database using psql."""
    host, port, user, password, dbname = extract_credentials(url)
    if not re.fullmatch(r"[A-Za-z0-9_]+", dbname):
        raise ValueError(f"Invalid database name: {dbname!r}")

    pg_bin = find_pg_bin()
    print(f"  Target DB   : {host}:{port}/{dbname}")
    print(f"  Dump file   : {dump_path.name}")

    if dry_run:
        print("  [dry-run] Would terminate connections, drop, recreate, and restore.")
        return

    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password

    # Terminate active connections
    print("\n[1/4] Terminating active connections...")
    term_sql = (
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{dbname}' AND pid <> pg_backend_pid();"
    )
    subprocess.run(
        [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user, "-d", "postgres", "-c", term_sql],
        env=env,
        capture_output=True,
        text=True,
    )

    print("[2/4] Dropping existing database...")
    subprocess.run(
        [
            str(pg_bin / "psql"),
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {dbname};",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    print("[3/4] Creating fresh database...")
    subprocess.run(
        [
            str(pg_bin / "psql"),
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            "postgres",
            "-c",
            f"CREATE DATABASE {dbname};",
        ],
        env=env,
        capture_output=True,
        text=True,
    )

    print("[4/4] Restoring database...")
    r = subprocess.run(
        [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user, "-d", dbname, "-f", str(dump_path)],
        env=env,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql restore failed:\n{r.stderr[-2000:]}")
    print("  + Database restored successfully.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore SQLite/PostgreSQL + FAISS + metadata")
    parser.add_argument("--backup-dir", required=True, help="Backup directory (name or path under backups/)")
    parser.add_argument("--url", default=None, help="Target DB URL or SQLite file path")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without applying")
    parser.add_argument("--no-db", action="store_true", help="Restore FAISS only, skip DB")
    args = parser.parse_args()

    backup_dir = Path(args.backup_dir)
    if not backup_dir.is_absolute():
        backup_dir = ROOT / "backups" / backup_dir
    if not backup_dir.exists():
        print(f"x Backup directory not found: {backup_dir}")
        return 1

    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"x No manifest.json in {backup_dir}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print("=" * 64)
    print("  Face Recognition AI — System Restore")
    print("=" * 64)
    print(f"  Backup      : {backup_dir.name}")
    print(f"  Created     : {manifest.get('created_at', 'unknown')}")

    print("\nVerifying backup integrity...")
    if not verify_artifacts(backup_dir, manifest):
        print("\nx Backup failed integrity verification — refusing to restore.")
        return 1

    db_info = manifest.get("database", {})
    db_type = db_info.get("type", "postgres" if db_info.get("dump_file", "").endswith(".sql") else "sqlite")

    try:
        if not args.no_db:
            dump_file = db_info.get("dump_file")
            dump_path = backup_dir / dump_file
            if not dump_path.exists():
                print(f"x Dump file not found: {dump_path}")
                return 1

            if db_type == "sqlite":
                target_sqlite = Path(args.url) if args.url else DEFAULT_SQLITE_PATH
                restore_sqlite_db(dump_path, target_sqlite, dry_run=args.dry_run)
            else:
                target_url = args.url or db_info.get("url_redacted")
                if not target_url or "***" in target_url:
                    print("x PostgreSQL target URL must be explicitly supplied with credentials via --url")
                    return 1
                restore_postgres_db(dump_path, target_url, dry_run=args.dry_run)

        # ── 2. Restore FAISS + Metadata ────────────────────────
        print("\nRestoring FAISS vector index + metadata...")
        EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("faiss.index", "metadata.json"):
            src = backup_dir / name
            dst = EMBEDDINGS_DIR / name
            if src.exists():
                if args.dry_run:
                    print(f"  [dry-run] Would copy {name} -> {dst}")
                else:
                    shutil.copy2(src, dst)
                    print(f"  + Restored: {name} ({src.stat().st_size:,} bytes)")

        print("\n" + "=" * 64)
        print("  System restore complete!")
        print("=" * 64)
        return 0
    except Exception as exc:
        print(f"\nx Restore failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
