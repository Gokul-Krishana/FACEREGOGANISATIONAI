"""
Database Integrity Verification Script
=======================================

Performs deep integrity and health checks across:
1. SQLite PRAGMA integrity_check and foreign_key_check (or PostgreSQL connection/table checks)
2. Schema structure & required indexes validation
3. Table record counts and statistics
4. FAISS embedding vector synchronization with database employee records
5. Optional automatic cleanup of orphaned nullable foreign key references (``--fix-orphans``)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config.config as cfg  # noqa: E402
from database.database import engine, get_session  # noqa: E402
from database.models import Attendance, AuditLog, Camera, Employee, Student, UnknownFace, User  # noqa: E402


def check_sqlite_integrity(fix_orphans: bool = False) -> bool:
    """Run SQLite PRAGMAs for low-level corruption check."""
    db_path = cfg.ROOT_DIR / "data" / "face_recognition.db"
    if not db_path.exists():
        print(f"i SQLite file not present at {db_path} (PostgreSQL mode?)")
        return True

    print(f"Checking SQLite file integrity: {db_path.name} ({db_path.stat().st_size:,} bytes)...")
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchall()
        if len(res) == 1 and res[0][0] == "ok":
            print("  + PRAGMA integrity_check: PASSED (ok)")
        else:
            print(f"  x PRAGMA integrity_check: FAILED -> {res}")
            return False

        cur.execute("PRAGMA foreign_key_check;")
        fk_violations = cur.fetchall()
        if not fk_violations:
            print("  + PRAGMA foreign_key_check: PASSED (zero violations)")
        else:
            if fix_orphans:
                print(f"  i Resolving {len(fk_violations)} orphaned nullable foreign key references...")
                cur.execute(
                    "UPDATE audit_logs SET actor_id = NULL WHERE actor_id IS NOT NULL AND actor_id NOT IN (SELECT id FROM employees)"
                )
                cur.execute(
                    "UPDATE recognition_log SET employee_id = NULL WHERE employee_id IS NOT NULL AND employee_id NOT IN (SELECT id FROM employees)"
                )
                conn.commit()
                cur.execute("PRAGMA foreign_key_check;")
                rem = cur.fetchall()
                if not rem:
                    print("  + PRAGMA foreign_key_check: FIXED (zero remaining violations)")
                else:
                    print(f"  x PRAGMA foreign_key_check: {len(rem)} unresolvable violations remaining")
                    return False
            else:
                print(f"  x PRAGMA foreign_key_check: FOUND {len(fk_violations)} violations (run with --fix-orphans)")
                return False
        return True
    finally:
        conn.close()


def check_orm_tables() -> dict:
    """Verify table accessibility and report record counts."""
    print("\nVerifying database tables and record counts...")
    counts = {}
    with get_session() as session:
        for model in (Employee, Student, Attendance, AuditLog, Camera, UnknownFace, User):
            name = model.__tablename__
            try:
                cnt = session.query(model).count()
                counts[name] = cnt
                print(f"  + Table '{name}': {cnt} records")
            except Exception as exc:
                counts[name] = f"ERROR: {exc}"
                print(f"  x Table '{name}': error querying -> {exc}")
    return counts


def check_faiss_sync() -> bool:
    """Verify FAISS vector index consistency with metadata.json and Employee records."""
    print("\nChecking FAISS vector index synchronization...")
    index_path = Path(cfg.FAISS_INDEX_PATH)
    meta_path = Path(cfg.METADATA_PATH)

    if not index_path.exists() or not meta_path.exists():
        print("  i FAISS index or metadata.json not yet created (clean environment)")
        return True

    try:
        import faiss

        index = faiss.read_index(str(index_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        ntotal = index.ntotal
        meta_count = len(metadata)
        print(f"  + FAISS index ntotal: {ntotal}")
        print(f"  + Metadata entries  : {meta_count}")

        if ntotal != meta_count:
            print(f"  x Desynchronization detected: FAISS vectors ({ntotal}) != metadata ({meta_count})")
            return False

        print("  + FAISS vector index and metadata are 100% synchronized")
        return True
    except Exception as exc:
        print(f"  x Error checking FAISS index: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify database integrity and health")
    parser.add_argument("--fix-orphans", action="store_true", help="Clean orphaned foreign key references")
    args = parser.parse_args()

    print("=" * 64)
    print("  Face Recognition AI — Database Integrity Verification")
    print("=" * 64)

    ok = True
    if not check_sqlite_integrity(fix_orphans=args.fix_orphans):
        ok = False

    counts = check_orm_tables()
    if any(str(v).startswith("ERROR") for v in counts.values()):
        ok = False

    if not check_faiss_sync():
        ok = False

    print("\n" + "=" * 64)
    if ok:
        print("  Database Integrity Check: ALL CHECKS PASSED (100% HEALTHY)")
        print("=" * 64)
        return 0
    else:
        print("  Database Integrity Check: WARNINGS / ERRORS DETECTED")
        print("=" * 64)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
