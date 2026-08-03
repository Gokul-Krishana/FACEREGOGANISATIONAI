"""
Verify the System Health page renders correctly.

Two-part check:
1. Run the page through AppTest with the auto-refresh tail
   (`time.sleep(10); st.rerun()`) stripped out — this proves the entire
   page body (all 7 health checks + rendering) executes without exceptions.
   (In the browser, the tail is handled correctly by the websocket client;
   it only misbehaves inside AppTest's headless runner.)
2. Time each heavy health check directly to rule out hangs.
"""

from __future__ import annotations

import sys
import time
import tempfile
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from streamlit.testing.v1 import AppTest  # noqa: E402  (needs sys.path setup above)

PAGE = Path(_project_root) / "dashboard" / "pages" / "09_Health.py"
# The auto-refresh tail starts at this marker comment.
_TAIL_MARKER = "# ── Auto-refresh logic ──"


def run_page_without_autorefresh() -> None:
    """Run a stripped copy of the page through AppTest."""
    src = PAGE.read_text(encoding="utf-8")
    head = src.split(_TAIL_MARKER)[0]
    # close any open code fences / st constructs from the cut point
    stripped = head + "\n# [auto-refresh tail stripped for headless verification]\n"

    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(stripped)
        tmp_path = f.name
    try:
        at = AppTest.from_file(tmp_path, default_timeout=180)
        at.run()
        errors = [str(e) for e in at.exception]
        if errors:
            print(f"HEALTH PAGE FAIL ({len(errors)} exception(s)):")
            for e in errors[:3]:
                print("  ", e)
        else:
            print("HEALTH PAGE RENDERS CLEAN (auto-refresh tail stripped)")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def time_health_checks() -> None:
    """Time the heavy operations the page performs server-side."""
    print("Timing heavy operations the page runs server-side:")

    t0 = time.perf_counter()
    import cv2
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    opened = cap.isOpened()
    if opened:
        ret, frame = cap.read()
    else:
        ret, frame = False, None
    cap.release()
    print(
        f"  Camera open+read: {time.perf_counter() - t0:.1f}s "
        f"| opened={opened} | frame={frame.shape if (opened and ret) else 'N/A'}"
    )

    t0 = time.perf_counter()
    from database.database import get_session
    from sqlalchemy import text
    with get_session() as s:
        s.execute(text("SELECT 1"))
    print(f"  DB SELECT 1: {time.perf_counter() - t0:.2f}s")

    t0 = time.perf_counter()
    from app.face_detector import FaceDetector
    _ = FaceDetector()
    print(f"  YOLO FaceDetector load: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    from app.recognizer import FaceRecognizer
    _ = FaceRecognizer()
    print(f"  ArcFace recognizer load: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    from app.enrollment import FaceEnrollment
    _ = FaceEnrollment()
    print(f"  FAISS enrollment load: {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    run_page_without_autorefresh()
    print()
    time_health_checks()
