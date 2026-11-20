"""
Dashboard Authentication & Role-Based Access Gate
=================================================

Provides session-backed authentication and role checks for the Streamlit
dashboard (`dashboard/app.py` and `dashboard/pages/*.py`), reusing the
existing ``users`` / ``roles`` / ``BruteForceProtection`` / ``AuditService``
infrastructure.

Usage inside a dashboard page (after ``st.set_page_config`` and module-level
helper definitions)::

    from dashboard.auth import ADMIN_ROLES, require_auth

    if not require_auth(allowed_roles=ADMIN_ROLES):
        st.stop()
"""

from __future__ import annotations

import logging
import sys
from typing import Iterable, Optional, Tuple

from sqlalchemy.orm import selectinload

from database.database import get_session, init_db
from database.models import Role, RoleName, User, _utcnow
from services.audit_service import AuditService
from services.brute_force_protection import BruteForceProtection


def _st():
    """Return the active ``streamlit`` module (supports test monkeypatching)."""
    st = sys.modules.get("streamlit")
    if st is None:
        import streamlit as st  # noqa: WPS433
    return st


logger = logging.getLogger(__name__)

ADMIN_ROLES: Tuple[str, ...] = (
    RoleName.SUPER_ADMIN.value,
    RoleName.COLLEGE_ADMIN.value,
)

OPERATOR_ROLES: Tuple[str, ...] = (
    RoleName.SUPER_ADMIN.value,
    RoleName.COLLEGE_ADMIN.value,
    RoleName.SECURITY.value,
)

_SESSION_USER_KEY = "auth_user"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not plain_password or not password_hash:
        return False
    try:
        import bcrypt

        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def has_any_users() -> bool:
    """Return ``True`` if at least one user account exists in the database."""
    try:
        with get_session() as session:
            return session.query(User.id).limit(1).first() is not None
    except Exception as exc:
        logger.warning("Could not query users table: %s", exc)
        return True  # Fail closed to login form rather than setup if DB check fails


def create_initial_admin(username: str, email: str, password: str) -> Tuple[bool, str]:
    """Bootstrap the first SUPER_ADMIN user when the database has no users."""
    username = (username or "").strip()
    email = (email or "").strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if "@" not in email or "." not in email:
        return False, "Please enter a valid email address."
    if len(password or "") < 8:
        return False, "Password must be at least 8 characters."

    try:
        init_db()
        with get_session() as session:
            if session.query(User.id).limit(1).first() is not None:
                return False, "An account already exists. Please sign in."

            roles_by_name = {}
            for role_enum in (RoleName.SUPER_ADMIN, RoleName.COLLEGE_ADMIN):
                role = session.query(Role).filter(Role.name == role_enum.value).first()
                if role is None:
                    role = Role(name=role_enum.value, description=f"{role_enum.value} role")
                    session.add(role)
                    session.flush()
                roles_by_name[role_enum.value] = role

            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                auth_method="local",
                is_active=True,
            )
            user.roles.append(roles_by_name[RoleName.SUPER_ADMIN.value])
            user.roles.append(roles_by_name[RoleName.COLLEGE_ADMIN.value])
            session.add(user)
            session.commit()
            session.refresh(user)

        AuditService.log(
            "USER_CREATED",
            f"Initial admin user '{username}' created via dashboard setup",
            operator=username,
        )
        return True, "Admin account created. You can now sign in."
    except Exception as exc:
        logger.exception("Failed to create initial admin user")
        return False, f"Could not create admin account: {exc}"


def authenticate_user(
    username: str,
    password: str,
    client_ip: str = "dashboard",
) -> Tuple[bool, Optional[dict], str]:
    """Validate credentials against the ``users`` table with lockout protection."""
    identifier = (username or "").strip()
    if not identifier or not password:
        return False, None, "Username and password are required."

    is_locked, lockout_msg = BruteForceProtection.is_locked_out(identifier, client_ip)
    if is_locked:
        BruteForceProtection.record_failed_attempt(identifier, client_ip, "streamlit-dashboard")
        AuditService.log(
            "USER_LOGIN",
            f"Dashboard login blocked (locked out) for '{identifier}'",
            operator=identifier,
        )
        return False, None, lockout_msg or "Account temporarily locked."

    with get_session() as session:
        user = (
            session.query(User)
            .options(selectinload(User.roles))
            .filter((User.username == identifier) | (User.email == identifier))
            .first()
        )
        if not user or not verify_password(password, str(user.password_hash or "")):
            BruteForceProtection.record_failed_attempt(identifier, client_ip, "streamlit-dashboard")
            AuditService.log(
                "USER_LOGIN",
                f"Failed dashboard login attempt for '{identifier}'",
                operator=identifier,
            )
            return False, None, "Invalid username or password."

        if not user.is_active:
            return False, None, "Account is disabled. Contact an administrator."

        user.last_login_at = _utcnow()  # type: ignore[assignment]
        session.commit()

        user_payload = {
            "id": user.id,
            "username": str(user.username),
            "email": str(user.email),
            "roles": [r.name for r in user.roles],
        }

    BruteForceProtection.record_successful_login(identifier, client_ip)
    AuditService.log(
        "USER_LOGIN",
        f"Dashboard login succeeded for '{user_payload['username']}'",
        operator=str(user_payload["username"]),
    )
    return True, user_payload, "OK"


def get_current_user() -> Optional[dict]:
    """Return the signed-in user dict from ``st.session_state``, or ``None``."""
    user = _st().session_state.get(_SESSION_USER_KEY)
    return user if isinstance(user, dict) and user.get("username") else None


def is_authenticated() -> bool:
    """Return ``True`` if a dashboard user is currently signed in."""
    return get_current_user() is not None


def user_has_role(user: Optional[dict], allowed_roles: Optional[Iterable[str]]) -> bool:
    """Return ``True`` if *user* holds at least one role in *allowed_roles*."""
    if not user:
        return False
    if allowed_roles is None:
        return True
    allowed = set(allowed_roles)
    if not allowed:
        return True
    user_roles = set(user.get("roles") or [])
    if RoleName.SUPER_ADMIN.value in user_roles:
        return True
    return bool(user_roles & allowed)


def logout() -> None:
    """Sign out the current dashboard user."""
    st = _st()
    user = get_current_user()
    if user:
        AuditService.log(
            "USER_LOGOUT",
            f"Dashboard logout for '{user.get('username')}'",
            operator=user.get("username", "dashboard"),
        )
    if _SESSION_USER_KEY in st.session_state:
        del st.session_state[_SESSION_USER_KEY]


def _render_login_form() -> None:
    """Render the Streamlit login form (or first-time admin setup form)."""
    st = _st()
    st.markdown("## 🔒 Sign In Required")
    st.caption("Authentication is required to access Face Recognition AI workflows.")

    if not has_any_users():
        st.info("No user accounts exist yet. Create the initial administrator account to continue.")
        with st.form("dashboard_initial_admin_form", clear_on_submit=False):
            new_user = st.text_input("Admin Username", value="admin")
            new_email = st.text_input("Admin Email", value="admin@college.edu")
            new_pw = st.text_input("Password (min 8 chars)", type="password")
            confirm_pw = st.text_input("Confirm Password", type="password")
            submitted = st.form_submit_button("Create Admin Account", type="primary")
            if submitted:
                if new_pw != confirm_pw:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = create_initial_admin(new_user, new_email, new_pw)
                    if ok:
                        ok_login, user_payload, _ = authenticate_user(new_user, new_pw)
                        if ok_login and user_payload:
                            st.session_state[_SESSION_USER_KEY] = user_payload
                            st.success("Administrator account created and signed in.")
                            st.rerun()
                        else:
                            st.success(msg)
                            st.rerun()
                    else:
                        st.error(msg)
        return

    with st.form("dashboard_login_form", clear_on_submit=False):
        username = st.text_input("Username or Email", placeholder="admin")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary")
        if submitted:
            ok, user_payload, message = authenticate_user(username, password)
            if ok and user_payload:
                st.session_state[_SESSION_USER_KEY] = user_payload
                st.rerun()
            else:
                st.error(message)


def _render_sidebar_user_controls(user: dict) -> None:
    """Show signed-in user info and Logout button in the sidebar."""
    st = _st()
    roles = ", ".join(user.get("roles") or []) or "USER"
    st.sidebar.caption(f"👤 **{user.get('username')}** ({roles})")
    if st.sidebar.button("🚪 Sign Out", key="_dashboard_sign_out_btn", use_container_width=True):
        logout()
        st.rerun()


def require_auth(allowed_roles: Optional[Iterable[str]] = None) -> bool:
    """Enforce authentication (and optional role membership) on a dashboard page.

    Returns:
        ``True`` if the current session is authenticated and authorized.
        ``False`` otherwise (after rendering the login screen or access error).
    """
    st = _st()
    try:
        init_db()
    except Exception as exc:
        logger.debug("Dashboard init_db check warning: %s", exc)

    user = get_current_user()
    if user is None:
        _render_login_form()
        return False

    _render_sidebar_user_controls(user)

    if not user_has_role(user, allowed_roles):
        st.error(
            "⛔ Access Denied — your account does not have the required role "
            "to access this administrative page."
        )
        return False

    return True
