"""
Employee Data Cleanup — Duplicate Detection & Merge
====================================================

Finds and resolves duplicate employee records (same display name,
case-insensitive) and stale FAISS references left over from legacy
data / benchmark runs.

The recognition pipeline resolves employees by *name* (the FAISS
metadata label), so duplicate names cause ``get_by_name`` to return
whichever row SQLAlchemy happens to pick first — which may be the
wrong record and can silently break attendance attribution.

Modes
-----
    # Dry run (default) — report only, change nothing
    python scripts/dedupe_employees.py

    # Apply the merge
    python scripts/dedupe_employees.py --apply

    # Also clean up employees whose faiss_id no longer exists in FAISS
    python scripts/dedupe_employees.py --apply --clean-stale

What it does (with --apply)
---------------------------
1. Groups employees by normalized name (lowercase, stripped).
2. For each group with > 1 member, keeps the "best" record:
   - the one with a valid ``faiss_id`` (i.e. present in the FAISS
     metadata), otherwise
   - the earliest-created record.
3. Re-points ``attendance`` and ``recognition_log`` rows from the
   removed employee(s) to the kept record (historical data is not
   lost — it is attributed to the survivor).
4. Deletes the duplicate rows.
5. With ``--clean-stale``, additionally removes employees whose
   ``faiss_id`` is set but does not exist in the FAISS index metadata
   (benchmark pollution), and removes their embedding label from FAISS.

The script is idempotent: running it again after a successful merge
reports no duplicates.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

# UTF-8 output (Windows consoles default to cp1252, which breaks on emoji)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure project root is on sys.path so we can import project modules
# (scripts/ is not a package; running `python scripts/dedupe_employees.py`
# puts scripts/ — not the project root — on sys.path)
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config.config as cfg  # noqa: E402  (needs sys.path setup above)
from database.database import get_session  # noqa: E402
from database.models import Attendance, Employee, RecognitionLog  # noqa: E402
from database.repository import EmployeeRepo  # noqa: E402


# ── FAISS helpers ──────────────────────────────────────────────────


def load_faiss_names() -> Dict[str, int]:
    """Return ``{name: faiss_id}`` from the FAISS metadata file.

    Empty dict if the metadata file is missing or unreadable.
    """
    meta_path = Path(cfg.METADATA_PATH)
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    result: Dict[str, int] = {}
    for entry in data:
        name = entry.get("name")
        fid = entry.get("id")
        if name is not None and fid is not None:
            result[str(name)] = int(fid)
    return result


def valid_faiss_ids() -> set:
    """Return the set of faiss_ids that currently exist in FAISS."""
    names = load_faiss_names()
    return set(names.values())


# ── Duplicate detection ──────────────────────────────────────────


def find_duplicate_groups(employees: List[Employee]) -> List[List[Employee]]:
    """Group employees by normalized name; return groups with >1 member."""
    by_name: Dict[str, List[Employee]] = defaultdict(list)
    for emp in employees:
        by_name[emp.name.strip().lower()].append(emp)

    groups = [members for members in by_name.values() if len(members) > 1]
    # Sort each group deterministically (id ascending)
    for group in groups:
        group.sort(key=lambda e: e.id)
    return groups


def pick_survivor(group: List[Employee], valid_ids: set) -> Employee:
    """Pick the record to keep from a duplicate group.

    Prefers the member with a valid FAISS id, then the earliest id.
    """
    for emp in group:
        if emp.faiss_id is not None and emp.faiss_id in valid_ids:
            return emp
    return group[0]


# ── Merge logic ──────────────────────────────────────────────────


def merge_group(session, group: List[Employee], survivor: Employee) -> int:
    """Re-point dependent rows and delete duplicates in one group.

    Returns the number of duplicate rows deleted.
    """
    removed_ids = [emp.id for emp in group if emp.id != survivor.id]
    if not removed_ids:
        return 0

    # Re-point attendance records
    session.query(Attendance).filter(Attendance.employee_id.in_(removed_ids)).update(
        {"employee_id": survivor.id}, synchronize_session=False
    )

    # Re-point recognition logs
    session.query(RecognitionLog).filter(RecognitionLog.employee_id.in_(removed_ids)).update(
        {"employee_id": survivor.id}, synchronize_session=False
    )

    # Delete duplicates
    session.query(Employee).filter(Employee.id.in_(removed_ids)).delete(synchronize_session=False)
    session.commit()
    return len(removed_ids)


def clean_stale_faiss_ids(session, employees: List[Employee], valid_ids: set) -> int:
    """Remove employees whose faiss_id is stale (not in FAISS).

    Their embedding label is also removed from FAISS if present.
    Employees that still have dependent rows (attendance / recognition
    logs) are skipped and reported — deleting them would violate
    foreign-key constraints on PostgreSQL. Returns the number of rows
    deleted.
    """
    stale = [emp for emp in employees if emp.faiss_id is not None and emp.faiss_id not in valid_ids]
    if not stale:
        return 0

    # Attempt FAISS label removal first (best-effort, never fatal)
    try:
        from app.enrollment import FaceEnrollment

        enrollment = FaceEnrollment()
        for emp in stale:
            try:
                enrollment.remove_by_name(emp.name)
            except Exception:
                pass  # logged by remove_by_name internally
    except Exception:
        pass

    # Skip employees that still own attendance / recognition history —
    # deleting them would raise an IntegrityError on PostgreSQL (SQLite
    # silently allows it, masking the problem).
    safe = []
    for emp in stale:
        has_attendance = (
            session.query(Attendance.id).filter(Attendance.employee_id == emp.id).first()
        ) is not None
        has_logs = (
            session.query(RecognitionLog.id).filter(RecognitionLog.employee_id == emp.id).first()
        ) is not None
        if has_attendance or has_logs:
            print(
                f"      ↳ SKIP id={emp.id} ({emp.employee_id!r}) — has attendance/recognition history "
                f"(re-point or merge first)"
            )
        else:
            safe.append(emp)

    if not safe:
        return 0

    ids = [emp.id for emp in safe]
    session.query(Employee).filter(Employee.id.in_(ids)).delete(synchronize_session=False)
    session.commit()
    return len(ids)


# ── Main ─────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the merge (default is a dry run that only reports).",
    )
    parser.add_argument(
        "--clean-stale",
        action="store_true",
        help="Also delete employees whose faiss_id no longer exists in FAISS.",
    )
    args = parser.parse_args()

    with get_session() as session:
        employees = EmployeeRepo.get_all(session)
        valid_ids = valid_faiss_ids()

        print("=" * 72)
        print("  EMPLOYEE DATA CLEANUP — Face Recognition AI")
        print("=" * 72)
        print(f"  Total employee records : {len(employees)}")
        print(f"  FAISS metadata entries : {len(load_faiss_names())}")
        print(f"  Mode                   : {'APPLY' if args.apply else 'DRY RUN (no changes)'}")
        print("=" * 72)

        groups = find_duplicate_groups(employees)
        if not groups:
            print("\n  ✅ No duplicate employee names found.")
        else:
            print(f"\n  ⚠️  {len(groups)} duplicate name group(s) found:")
            for group in groups:
                survivor = pick_survivor(group, valid_ids)
                print(f'\n    Group "{group[0].name}":')
                for emp in group:
                    marker = "  ← KEEP" if emp.id == survivor.id else "  (duplicate)"
                    stale = ""
                    if emp.faiss_id is not None and emp.faiss_id not in valid_ids:
                        stale = "  [stale faiss_id]"
                    print(
                        f"      id={emp.id:>4} emp_id={emp.employee_id!r:>12} "
                        f"faiss_id={emp.faiss_id!r}{marker}{stale}"
                    )

        # Stale faiss_id report
        stale_rows = [emp for emp in employees if emp.faiss_id is not None and emp.faiss_id not in valid_ids]
        if stale_rows:
            print(f"\n  ⚠️  {len(stale_rows)} employee(s) with stale faiss_id (not in FAISS):")
            for emp in stale_rows:
                print(f"      id={emp.id:>4} emp_id={emp.employee_id!r:>12} faiss_id={emp.faiss_id}")

        # ── Apply phase ────────────────────────────────────────
        if not args.apply:
            print("\n  Dry run complete. Re-run with --apply to merge.")
            return 0

        total_deleted = 0
        if groups:
            for group in groups:
                survivor = pick_survivor(group, valid_ids)
                deleted = merge_group(session, group, survivor)
                total_deleted += deleted
                print(
                    f'  ✅ Merged "{survivor.name}" group: '
                    f"kept id={survivor.id}, deleted {deleted} duplicate(s)"
                )

        if args.clean_stale:
            # Guard: never run a data-destroying sweep when the FAISS
            # metadata is missing or empty — `valid_faiss_ids()` would
            # return an empty set and every faiss_id would look stale.
            faiss_names = load_faiss_names()
            if not faiss_names:
                print(
                    "  ⛔ --clean-stale ABORTED: embeddings/metadata.json is missing or empty. "
                    "Refusing to delete anything."
                )
            else:
                # Re-read employees after merges
                employees = EmployeeRepo.get_all(session)
                valid_ids = set(faiss_names.values())
                stale = clean_stale_faiss_ids(session, employees, valid_ids)
                if stale:
                    print(f"  🧹 Removed {stale} employee(s) with stale faiss_id")
                else:
                    print("  ✅ No stale faiss_id records to remove.")

        print(f"\n  Done. Total duplicate rows deleted: {total_deleted}")
        print("  Attendance / recognition history was re-attributed to the kept record.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
