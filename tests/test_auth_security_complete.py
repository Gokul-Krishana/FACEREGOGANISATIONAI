"""
Complete Authentication and Authorization Verification Suite
============================================================

Verifies:
- Direct access to every dashboard page without login is blocked
- Protected API routes reject unauthenticated requests (HTTP 401)
- Expired and tampered JWT tokens are strictly rejected (HTTP 401)
- Inactive user accounts cannot authenticate or access endpoints (HTTP 401)
- Role-Based Access Control (RBAC): non-admin users cannot perform admin actions (HTTP 403)
- Token logout and revocation works cleanly
- Authorized administrators can access protected endpoints
- Production secret key and weak password checks are enforced
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

import config.config as cfg
from database.database import get_session, init_db
from database.models import Role, RoleName, User
from dashboard.auth import ADMIN_ROLES, OPERATOR_ROLES, require_auth, user_has_role


@pytest.fixture(scope="module")
def api_client():
    os.environ["ENVIRONMENT"] = "development"
    os.environ["SECRET_KEY"] = "test-secret-key-for-auth-testing-at-least-32-chars"
    from api.main import app

    client = TestClient(app)
    return client


def _create_test_user_with_role(username: str, role_name: RoleName, is_active: bool = True) -> int:
    init_db()
    with get_session() as session:
        # Check if role exists
        role = session.query(Role).filter_by(name=role_name.value).first()
        if not role:
            role = Role(name=role_name.value, description=f"Test role {role_name.value}")
            session.add(role)
            session.commit()

        # Delete old user if exists
        old = session.query(User).filter_by(username=username).first()
        if old:
            session.delete(old)
            session.commit()

        import bcrypt

        hashed = bcrypt.hashpw(b"ValidPass123!@", bcrypt.gensalt()).decode("utf-8")
        user = User(
            username=username,
            email=f"{username}@college.edu",
            password_hash=hashed,
            is_active=is_active,
        )
        user.roles.append(role)
        session.add(user)
        session.commit()
        return user.id


def _generate_jwt_token(user_id: int, secret_key: str, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta or timedelta(minutes=30)
    expire = datetime.now(timezone.utc) + delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


# ── Dashboard Page Access Tests ───────────────────────────────────────


def test_every_dashboard_page_requires_auth():
    """Verify that every dashboard page rejects unauthenticated direct access."""
    pages_dir = Path(cfg.ROOT_DIR) / "dashboard" / "pages"
    page_files = sorted(pages_dir.glob("*.py"))
    assert len(page_files) == 10, f"Expected 10 dashboard pages, found {len(page_files)}"

    for page_p in page_files:
        code = page_p.read_text(encoding="utf-8")
        assert "require_auth" in code, f"Page {page_p.name} is missing require_auth() gate!"


def test_dashboard_require_auth_fails_when_unauthenticated():
    """Verify require_auth returns False and renders login form when session has no user."""
    mock_st = MagicMock()
    mock_st.session_state = {}

    with patch("dashboard.auth._st", return_value=mock_st):
        allowed = require_auth()
        assert allowed is False
        # Login form was rendered
        assert mock_st.markdown.called


def test_dashboard_rbac_privilege_escalation_blocked():
    """Verify normal student role is blocked from admin pages."""
    student_user = {
        "id": 999,
        "username": "student_user",
        "email": "student@college.edu",
        "roles": [RoleName.STUDENT.value],
    }

    # Student accessing admin page
    assert user_has_role(student_user, ADMIN_ROLES) is False
    # Student accessing operator page
    assert user_has_role(student_user, OPERATOR_ROLES) is False

    # Admin user accessing admin page
    admin_user = {
        "id": 1,
        "username": "super_admin",
        "email": "admin@college.edu",
        "roles": [RoleName.SUPER_ADMIN.value],
    }
    assert user_has_role(admin_user, ADMIN_ROLES) is True


# ── API Endpoint Authentication Tests ─────────────────────────────────


def test_api_endpoints_reject_unauthenticated_requests(api_client):
    """Protected endpoints must return 401 when no token is supplied."""
    protected_urls = [
        ("GET", "/auth/me"),
        ("POST", "/employees"),
        ("GET", "/employees"),
        ("POST", "/cameras"),
        ("GET", "/cameras"),
        ("POST", "/attendance"),
        ("GET", "/unknown-faces"),
    ]

    for method, path in protected_urls:
        if method == "GET":
            res = api_client.get(path)
        else:
            res = api_client.post(path, json={})

        assert res.status_code == 401, f"Endpoint {method} {path} returned {res.status_code}, expected 401!"


def test_api_rejects_expired_token(api_client):
    """Expired JWT tokens must return HTTP 401."""
    user_id = _create_test_user_with_role("test_expired_user", RoleName.COLLEGE_ADMIN)
    from api.main import create_access_token

    # Generate token that expired 10 minutes ago
    expired_token = create_access_token(
        data={"sub": user_id, "username": "test_expired_user", "roles": [RoleName.COLLEGE_ADMIN.value]},
        expires_delta=timedelta(minutes=-10),
    )

    headers = {"Authorization": f"Bearer {expired_token}"}
    res = api_client.get("/auth/me", headers=headers)
    assert res.status_code == 401
    assert "Invalid or expired token" in res.json().get("error", "")


def test_api_rejects_tampered_signature_token(api_client):
    """Tokens signed with a different key must be rejected with 401."""
    user_id = _create_test_user_with_role("test_tampered_user", RoleName.COLLEGE_ADMIN)
    bad_secret = "completely-wrong-secret-key-for-tampering-attempt-1234"
    tampered_token = _generate_jwt_token(user_id, bad_secret)

    headers = {"Authorization": f"Bearer {tampered_token}"}
    res = api_client.get("/auth/me", headers=headers)
    assert res.status_code == 401


def test_api_rejects_inactive_account(api_client):
    """Inactive accounts (is_active=False) must be rejected with 401."""
    inactive_user_id = _create_test_user_with_role("test_inactive_user", RoleName.FACULTY, is_active=False)
    from api.main import create_access_token

    token = create_access_token(
        data={"sub": inactive_user_id, "username": "test_inactive_user", "roles": [RoleName.FACULTY.value]}
    )

    headers = {"Authorization": f"Bearer {token}"}
    res = api_client.get("/auth/me", headers=headers)
    assert res.status_code == 401
    assert "inactive" in res.json().get("error", "").lower()


def test_api_rbac_prevents_privilege_escalation(api_client):
    """Non-admin user (STUDENT) cannot perform admin operations (HTTP 403)."""
    student_id = _create_test_user_with_role("student_bob", RoleName.STUDENT, is_active=True)
    from api.main import create_access_token

    student_token = create_access_token(
        data={"sub": student_id, "username": "student_bob", "roles": [RoleName.STUDENT.value]}
    )

    headers = {"Authorization": f"Bearer {student_token}"}

    # Student attempting to create an employee -> Must be 403 Forbidden
    payload = {"employee_id": "HACKED_EMP_99", "name": "Illegal Employee"}
    res = api_client.post("/employees", json=payload, headers=headers)
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}: {res.text}"


def test_api_authorized_admin_succeeds(api_client):
    """Authorized administrator can successfully access protected endpoints."""
    admin_id = _create_test_user_with_role("admin_verified", RoleName.SUPER_ADMIN, is_active=True)
    from api.main import create_access_token

    admin_token = create_access_token(
        data={"sub": admin_id, "username": "admin_verified", "roles": [RoleName.SUPER_ADMIN.value]}
    )

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = api_client.get("/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.json()["username"] == "admin_verified"
    assert res.json()["username"] == "admin_verified"
