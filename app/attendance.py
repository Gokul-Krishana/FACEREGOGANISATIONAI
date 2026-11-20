"""
Attendance Tracking Module — CSV Logging
==========================================

Records face-recognition attendance events with timestamps.
Each day gets its own CSV file.

Features:
- Mark attendance (once per person per day).
- Query today's attendance, any date's attendance, or all records.
- Aggregate statistics.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
import threading
from typing import Dict, List, Optional

import config.config as cfg


class AttendanceTracker:
    """Per‑day CSV attendance logger.

    Attributes:
        log_dir: Directory where daily CSV files are stored.
    """

    def __init__(self, log_dir: str | Path = cfg.ATTENDANCE_DIR) -> None:
        """Initialise the tracker.

        Args:
            log_dir: Directory to store attendance CSV files.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────

    def mark(self, name: str, confidence: float = 1.0, employee_id: Optional[str] = None) -> bool:
        """Record attendance for a person **once per day** (thread-safe).

        Args:
            name: Person's display name.
            confidence: Recognition confidence score.
            employee_id: Optional unique identifier used to distinguish
                people who share the same display name.

        Returns:
            ``True`` if the record was added; ``False`` if already
            marked today.
        """
        with self._lock:
            today_path = self._today_path()

            # Avoid duplicates for the same person today
            if self._is_marked(today_path, name, employee_id=employee_id):
                return False

            now = datetime.now()
            with open(today_path, "a", newline="") as f:
                writer = csv.writer(f)
                if f.tell() == 0:  # empty file → write header
                    writer.writerow(["name", "timestamp", "confidence", "employee_id"])
                writer.writerow([name, now.isoformat(), f"{confidence:.4f}", employee_id or ""])
            return True

    def today(self) -> List[Dict[str, str]]:
        """Return all attendance records for today."""
        return self._read_csv(self._today_path())

    def by_date(self, target_date: date) -> List[Dict[str, str]]:
        """Return attendance records for a specific date."""
        file_path = self.log_dir / f"{target_date.isoformat()}.csv"
        return self._read_csv(file_path)

    def all_records(self) -> Dict[str, List[Dict[str, str]]]:
        """Return all attendance records, keyed by date string."""
        records: Dict[str, List[Dict[str, str]]] = {}
        for csv_file in sorted(self.log_dir.glob("*.csv")):
            records[csv_file.stem] = self._read_csv(csv_file)
        return records

    def statistics(self) -> Dict[str, int]:
        """Return aggregate attendance statistics."""
        all_records = self.all_records()
        unique_names: set = set()
        total = 0
        for records in all_records.values():
            for r in records:
                unique_names.add(r.get("name", ""))
                total += 1
        today_count = len(self.today())
        return {
            "total_days_attended": len(all_records),
            "unique_persons_seen": len(unique_names),
            "today_count": today_count,
            "total_records": total,
        }

    # ── Internals ─────────────────────────────────────────────

    def _today_path(self) -> Path:
        return self.log_dir / f"{date.today().isoformat()}.csv"

    def _read_csv(self, file_path: Path) -> List[Dict[str, str]]:
        if not file_path.exists():
            return []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def _is_marked(self, file_path: Path, name: str, employee_id: Optional[str] = None) -> bool:
        if not file_path.exists():
            return False
        with open(file_path, "r") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if not row:
                    continue
                row_emp_id = row[3].strip() if len(row) >= 4 else ""
                if employee_id and row_emp_id:
                    if row_emp_id == employee_id:
                        return True
                elif not employee_id and row[0].strip() == name:
                    return True
                elif employee_id and not row_emp_id and row[0].strip() == name:
                    # Legacy 3-column CSV row without employee_id
                    return True
        return False
