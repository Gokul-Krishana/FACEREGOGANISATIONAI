"""
Restore — PostgreSQL + FAISS + Metadata
=========================================

Restores a snapshot created by ``scripts/backup.py``:

    1. PostgreSQL database  (psql ← plain SQL dump)
    2. FAISS vector index   (embeddings/faiss.index)
    3. Embedding metadata   (embeddings/metadata.json)

By default the database is restored into the URL recorded in the
manifest. Use ``--url`` to restore into a different database (e.g. a
staging copy). FAISS artifacts are restored into the project's
``embeddings/`` directory — the app must be restarted after restore so
the index is reloaded from disk.

Usage:
    python scripts/restore.py --backup-dir backups/backup_20260731_120000
    python scripts/restore.py --backup-dir <dir> --url postgresql://user:pass@host:5432/db
    python scripts/restore.py --backup-dir <dir> --dry-run

NOTE: The target database is dropped and recreated. The application must
be stopped first, otherwise DROP DATABASE fails due to active connections.
"""

from __future__ import annotations

import argparse
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

EMBEDDINGS_DIR = cfg.EMBEDDINGS_DIR

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
    raise FileNotFoundError(
        "psql not found. Install PostgreSQL or add its bin directory to PATH."
    )


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


def resolve_target_url(manifest: dict, args) -> str | None:
    """Determine the target DB URL. Returns None if it can't be resolved."""
    if args.url:
        return args.url
    redacted = manifest.get("database", {}).get("url_redacted", "")
    if redacted and "***" not in redacted:
        # Manifest has a usable (unredacted) URL
        return redacted
    # Redacted or missing — we must not guess a password silently
    print("  x The manifest does not contain a usable database URL (password is redacted).")
    print("    Pass the target explicitly:  --url postgresql://user:pass@host:5432/db")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore PostgreSQL + FAISS + metadata")
    parser.add_argument("--backup-dir", required=True,
                        help="Backup directory (name or path under backups/)")
    parser.add_argument("--url", default=None,
                        help="Target PostgreSQL URL (required if manifest URL is redacted)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be restored without changing anything")
    parser.add_argument("--no-db", action="store_true",
                        help="Restore FAISS/metadata only, skip database restore")
    args = parser.parse_args()

    # Resolve backup dir
    backup_dir = Path(args.backup_dir)
    if not backup_dir.is_absolute():
        backup_dir = ROOT / "backups" / backup_dir
    if not backup_dir.exists():
        print(f"x Backup directory not found: {backup_dir}")
        return 1

    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"x No manifest.json in {backup_dir} — not a valid backup")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print("=" * 64)
    print("  System Restore")
    print("=" * 64)
    print(f"  Backup      : {backup_dir.name}")
    print(f"  Created     : {manifest.get('created_at', 'unknown')}")

    # Integrity check first
    print("\nVerifying backup integrity...")
    if not verify_artifacts(backup_dir, manifest):
        print("\nx Backup failed integrity verification — refusing to restore.")
        return 1

    # ── 1. Database restore ────────────────────────────────────
    if not args.no_db:
        url = resolve_target_url(manifest, args)
        if url is None:
            return 1
        host, port, user, password, dbname = extract_credentials(url)
        if not re.fullmatch(r"[A-Za-z0-9_]+", dbname):
            print(f"x Invalid database name: {dbname!r}")
            return 1
        try:
            pg_bin = find_pg_bin()
        except FileNotFoundError as exc:
            print(f"x {exc}")
            return 1
        dump_path = backup_dir / manifest.get("database", {}).get(
            "dump_file", f"{dbname}.sql")
        if not dump_path.exists():
            print(f"x SQL dump not found: {dump_path}")
            return 1

        print(f"  Target DB   : {host}:{port}/{dbname}")
        print(f"  Dump file   : {dump_path.name}")

        if args.dry_run:
            print("  [dry-run] Would terminate connections, drop, recreate, and restore.")
        else:
            env = dict(os.environ)
            if password:
                env["PGPASSWORD"] = password

            # Terminate active connections so DROP DATABASE succeeds
            print("\n[1/4] Terminating active connections...")
            term_sql = (
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{dbname}' AND pid <> pg_backend_pid();"
            )
            subprocess.run(
                [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user,
                 "-d", "postgres", "-c", term_sql],
                env=env, capture_output=True, text=True,
            )

            print("[2/4] Dropping existing database...")
            r = subprocess.run(
                [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user,
                 "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {dbname};"],
                env=env, capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"  x DROP DATABASE failed:\n{r.stderr[-1500:]}")
                return 1

            print("[3/4] Creating fresh database...")
            r = subprocess.run(
                [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user,
                 "-d", "postgres", "-c", f"CREATE DATABASE {dbname};"],
                env=env, capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"  x CREATE DATABASE failed:\n{r.stderr[-1500:]}")
                return 1

            print("[4/4] Restoring dump...")
            r = subprocess.run(
                [str(pg_bin / "psql"), "-h", host, "-p", port, "-U", user,
                 "-d", dbname, "-f", str(dump_path)],
                env=env, capture_output=True, text=True,
            )
            if r.returncode != 0:
                print(f"  x psql restore failed:\n{r.stderr[-2000:]}")
                return 1
            print("  + Database restored")
    else:
        print("  [--no-db] Skipping database restore")

    # ── 2. FAISS + metadata restore ────────────────────────────
    print("\nRestoring FAISS index + metadata...")
    artifacts = manifest.get("artifacts", {})
    for name in ("faiss.index", "metadata.json"):
        artifact = artifacts.get(name, {})
        if not artifact.get("exists", True):
            print(f"  . {name}: not in backup — skipping")
            continue
        src = backup_dir / name
        if not src.exists():
            print(f"  . {name}: file missing from backup dir — skipping")
            continue
        if args.dry_run:
            print(f"  [dry-run] Would restore {src.name} -> {EMBEDDINGS_DIR}")
            continue
        dst = EMBEDDINGS_DIR / name
        shutil.copy2(src, dst)
        print(f"  + {name} -> {dst}")

    print("\n" + "=" * 64)
    if not args.dry_run:
        print("  Restore complete.")
        print("  ! Restart the app (Streamlit/API) so the FAISS index is reloaded.")
    else:
        print("  [dry-run] No changes made.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
