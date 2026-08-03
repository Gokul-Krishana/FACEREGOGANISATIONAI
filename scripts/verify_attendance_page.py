"""
Verify the Attendance page renders correctly.

The page calls ``webrtc_streamer(...)`` (from streamlit_webrtc) when the
default "Browser Webcam" mode is active. Inside AppTest the Streamlit
runtime is a Mock, so streamlit_webrtc raises
``Mock object has no attribute '_session_mgr'`` — this is an AppTest-only
limitation, not a page bug (in a real browser the websocket client provides
a real session manager).

This script neutralizes the webrtc call (the same path the page takes when
``streamlit-webrtc`` is not installed), strips the auto-refresh tail
(``time.sleep(5); st.rerun()`` loops forever inside AppTest's headless
runner), and proves the rest of the page — attendance table, stats,
history, export — renders without exceptions.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from streamlit.testing.v1 import AppTest  # noqa: E402  (needs sys.path setup above)

PAGE = Path(_project_root) / "dashboard" / "pages" / "05_Attendance.py"


def run_page_with_webrtc_neutralized() -> None:
    src = PAGE.read_text(encoding="utf-8")

    # Neutralize the webrtc call by replacing it with a no-op that still
    # leaves webrtc_ctx defined with the attributes the page reads.
    src = src.replace(
        "webrtc_ctx = webrtc_streamer(",
        "webrtc_ctx = type('Ctx', (), {'state': type('S', (), {'playing': False})})()\n                if False: webrtc_ctx = webrtc_streamer(",
        1,
    )

    # Strip the auto-refresh tail (same pattern as verify_health_page.py) —
    # inside AppTest, `time.sleep(5); st.rerun()` reruns forever until the
    # 180s AppTest timeout, which looks like a hang/failure.
    _AUTO_REFRESH_MARKER = "# ─── Auto-refresh ───"
    if _AUTO_REFRESH_MARKER in src:
        src = src.split(_AUTO_REFRESH_MARKER)[0]
        src += "\n# [auto-refresh tail stripped for headless verification]\n"

    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(src)
        tmp_path = f.name
    try:
        at = AppTest.from_file(tmp_path, default_timeout=180)
        at.run()
        errors = [str(e) for e in at.exception]
        if errors:
            print(f"ATTENDANCE PAGE FAIL ({len(errors)} exception(s)):")
            for e in errors[:3]:
                print("  ", e)
        else:
            print("ATTENDANCE PAGE RENDERS CLEAN (webrtc call neutralized)")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    run_page_with_webrtc_neutralized()
