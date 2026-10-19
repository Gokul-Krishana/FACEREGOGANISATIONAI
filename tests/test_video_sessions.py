"""
Tests for the /video/sessions endpoints (api/main.py)
=====================================================

Covers the REST surface of the live-video feature:

- Start/stop/list/status lifecycle, including idempotent START (one
  session per key) and 404s for unknown sessions/cameras.
- Session-key and source resolution (camera row -> ``cam-{id}`` with
  RTSP/HTTP streams mapped to ``ip_camera``, bare device index -> webcam).
- MJPEG endpoint auth (query-string JWT for browsers) and 404 handling.
- Permission enforcement (cameras:UPDATE) on mutating endpoints.

No physical camera or AI model is touched: the camera factory and the
shared recognition service are faked, and auth is seeded into the test
database with a real JWT so the actual permission-checking dependency
path is exercised.
"""

from __future__ import annotations

import time
from typing import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from database.database import get_session
from database.models import Permission, Role, User

# ── Fakes ──────────────────────────────────────────────────────────


class FakeCamera:
    def __init__(self, opens: bool = True) -> None:
        self.opens = opens
        self.released = False
        self._frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def open(self) -> bool:
        return self.opens

    def set_resolution(self, width: int, height: int) -> None:
        pass

    def read(self):
        time.sleep(0.005)
        return (not self.released), self._frame.copy()

    def release(self) -> None:
        self.released = True


class FakeRecognitionService:
    def process_frame_detailed(self, frame):
        return True, []


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture()
def seeded_user() -> Iterator[User]:
    """Create an active user holding cameras:UPDATE and read back a
    detached instance with the same id (used by dependency overrides)."""
    with get_session() as session:
        perm = Permission(resource="cameras", action="UPDATE")
        perm_read = Permission(resource="cameras", action="READ")
        role = Role(name="CAM_ADMIN", permissions=[perm, perm_read])
        user = User(
            username="vid_admin",
            email="vid_admin@example.com",
            password_hash="x",
            is_active=True,
            roles=[role],
        )
        session.add_all([perm, perm_read, role, user])
        session.commit()
        user_id = user.id
    try:
        with get_session() as session:
            yield session.get(User, user_id)
    finally:
        with get_session() as session:
            db_user = session.get(User, user_id)
            if db_user is not None:
                for role in list(db_user.roles):
                    # Clear the association before deleting so the unique
                    # (resource, action) index can be reused by the next test.
                    role.permissions = []
                    session.delete(role)
                session.delete(db_user)
            session.query(Permission).filter(
                Permission.resource == "cameras",
                Permission.action.in_(["UPDATE", "READ"]),
            ).delete(synchronize_session=False)
            session.commit()


@pytest.fixture()
def fake_camera(monkeypatch) -> FakeCamera:
    """Make every session open a FakeCamera and skip real AI models."""
    import services.live_camera_manager as lcm

    cam = FakeCamera()
    monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: cam)
    monkeypatch.setattr(lcm.live_camera_manager, "_get_service", lambda: FakeRecognitionService())
    yield cam
    lcm.live_camera_manager.stop_all()


@pytest.fixture()
def client(seeded_user, fake_camera) -> Iterator[TestClient]:
    """TestClient with JWT auth replaced by the seeded user.

    The permission-checking dependency (``require_permission``) still
    runs its real RBAC query against the test database.
    """
    api_main.app.dependency_overrides[api_main.get_current_user] = lambda: seeded_user
    with TestClient(api_main.app) as test_client:
        yield test_client
    api_main.app.dependency_overrides.clear()


# ── Session lifecycle ──────────────────────────────────────────────


class TestVideoSessionLifecycle:
    def test_start_stop_and_status(self, client: TestClient) -> None:
        resp = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 0})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["key"] == "webcam-0"
        assert payload["status"] in ("CONNECTING", "LIVE", "STOPPED", "ERROR")

        listed = client.get("/video/sessions")
        assert listed.status_code == 200
        assert any(s["key"] == "webcam-0" for s in listed.json()["sessions"])

        status = client.get("/video/sessions/webcam-0/status")
        assert status.status_code == 200
        assert status.json()["key"] == "webcam-0"

        stop = client.post("/video/sessions/webcam-0/stop")
        assert stop.status_code == 200
        assert stop.json() == {"key": "webcam-0", "status": "STOPPED"}

    def test_start_is_idempotent(self, client: TestClient) -> None:
        first = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 0})
        second = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 0})
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["key"] == second.json()["key"]

    def test_stop_unknown_session_404(self, client: TestClient) -> None:
        resp = client.post("/video/sessions/no-such-key/stop")
        assert resp.status_code == 404

    def test_status_unknown_session_404(self, client: TestClient) -> None:
        resp = client.get("/video/sessions/no-such-key/status")
        assert resp.status_code == 404

    def test_start_503_when_camera_cannot_open(self, client: TestClient, monkeypatch) -> None:
        import services.live_camera_manager as lcm

        monkeypatch.setattr(lcm, "create_camera", lambda *a, **kw: FakeCamera(opens=False))
        resp = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 1})
        assert resp.status_code == 503
        assert resp.json()["error"]


# ── Session-key / source resolution ────────────────────────────────


class TestSessionKeyResolution:
    def test_camera_row_rtsp_maps_to_ip_camera(self, client: TestClient) -> None:
        from database.models import Camera

        with get_session() as session:
            camera = Camera(
                name="Gate cam",
                camera_id="gate-1",
                stream_url="rtsp://10.0.0.5/stream1",
            )
            session.add(camera)
            session.commit()
            camera_id = camera.id
        try:
            resp = client.post("/video/sessions/start", json={"camera_id": camera_id})
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["key"] == f"cam-{camera_id}"
            assert payload["source_type"] == "ip_camera"
        finally:
            client.post(f"/video/sessions/cam-{camera_id}/stop")
            with get_session() as session:
                db_camera = session.get(Camera, camera_id)
                if db_camera is not None:
                    session.delete(db_camera)
                session.commit()

    def test_unknown_camera_row_404(self, client: TestClient) -> None:
        resp = client.post("/video/sessions/start", json={"camera_id": 999999})
        assert resp.status_code == 404

    def test_url_override_without_camera_row(self, client: TestClient) -> None:
        resp = client.post(
            "/video/sessions/start",
            json={"source_type": "ip_camera", "url": "rtsp://10.0.0.9/live"},
        )
        assert resp.status_code == 200
        assert resp.json()["source_type"] == "ip_camera"


# ── Permissions ────────────────────────────────────────────────────


class TestVideoSessionPermissions:
    def test_start_requires_auth(self, client: TestClient, seeded_user) -> None:
        api_main.app.dependency_overrides.pop(api_main.get_current_user, None)
        resp = client.post("/video/sessions/start", json={"source_type": "webcam"})
        assert resp.status_code == 401

    def test_start_requires_cameras_update(self, client: TestClient, seeded_user) -> None:
        # Strip the cameras:UPDATE permission, keep the user.
        with get_session() as session:
            db_user = session.get(User, seeded_user.id)
            for role in db_user.roles:
                role.permissions = [p for p in role.permissions if p.resource != "cameras"]
            session.commit()
        resp = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 3})
        assert resp.status_code == 403


# ── MJPEG endpoint ─────────────────────────────────────────────────


class TestVideoSessionMjpeg:
    def test_mjpeg_requires_valid_token(self, client: TestClient) -> None:
        resp = client.get("/video/sessions/webcam-0/mjpeg", params={"token": "bogus"})
        assert resp.status_code == 401

    def test_mjpeg_unknown_session_404(self, client: TestClient, seeded_user) -> None:
        from datetime import timedelta

        from api.main import create_access_token

        token = create_access_token(
            {"sub": str(seeded_user.id), "username": "vid_admin"},
            expires_delta=timedelta(minutes=5),
        )
        resp = client.get("/video/sessions/no-such-key/mjpeg", params={"token": token})
        assert resp.status_code == 404

    def test_mjpeg_streams_first_frame(self, client: TestClient) -> None:
        """The MJPEG generator emits a multipart chunk with a JPEG payload.

        The generator is infinite by design, so one chunk is pulled from
        it directly rather than through TestClient.stream (which cannot
        cancel a never-ending ASGI response).
        """
        import services.live_camera_manager as lcm

        start = client.post("/video/sessions/start", json={"source_type": "webcam", "device_id": 0})
        assert start.status_code == 200
        key = start.json()["key"]

        # Wait for the capture thread to deliver the first frame.
        deadline = time.time() + 3.0
        while time.time() < deadline:
            session = lcm.live_camera_manager.get(key)
            if session is not None and session.buffer.get()[0] is not None:
                break
            time.sleep(0.02)
        assert session is not None and session.buffer.get()[0] is not None

        chunk = next(lcm.live_camera_manager.mjpeg(key, fps=5, annotate=True))
        assert chunk.startswith(b"--frame\r\n")
        assert b"Content-Type: image/jpeg" in chunk
        assert b"\xff\xd8" in chunk  # JPEG SOI marker
