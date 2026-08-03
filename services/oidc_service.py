"""
OIDC Authentication Service
=============================

Provider-agnostic OpenID Connect integration for college SSO.

Supports any standard OIDC provider (Azure AD, Keycloak, Okta, Google)
by using the provider's well-known discovery endpoint.

Usage::

    from services.oidc_service import OIDCService

    oidc = OIDCService()
    redirect_url = await oidc.get_login_url(request)
    user_info = await oidc.handle_callback(request)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from fastapi import HTTPException, Request, status
from httpx import AsyncClient

from database.database import get_session
from database.models import Role, RoleName, User

logger = logging.getLogger(__name__)


@dataclass
class OIDCUserInfo:
    """Normalised user info returned by any OIDC provider."""

    sub: str  # Provider-specific user ID
    email: str
    username: str  # Preferred username or email local part
    name: str  # Display name
    provider: str  # e.g. "azure", "keycloak", "google"
    groups: List[str]  # Group memberships (for role mapping)
    mfa_performed: bool = False  # Whether MFA was performed at the IdP
    raw_claims: Optional[Dict] = None  # Full ID token claims for debugging


class OIDCService:
    """Provider-agnostic OIDC integration.

    Configured via environment variables (see ``.env.example``):

        OIDC_ISSUER_URL      — The OIDC well-known discovery URL
        OIDC_CLIENT_ID       — OIDC client ID
        OIDC_CLIENT_SECRET   — OIDC client secret
        OIDC_SCOPES          — Space-separated scopes (default: "openid profile email")
        OIDC_REDIRECT_URI    — Callback URL (e.g. https://api.college.edu/auth/callback)
    """

    def __init__(self) -> None:
        self._issuer_url = os.getenv("OIDC_ISSUER_URL", "")
        self._client_id = os.getenv("OIDC_CLIENT_ID", "")
        self._client_secret = os.getenv("OIDC_CLIENT_SECRET", "")
        self._scopes = os.getenv("OIDC_SCOPES", "openid profile email")
        self._redirect_uri = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")

        self._enabled = bool(self._issuer_url and self._client_id and self._client_secret)
        self._config: Optional[Dict[str, Any]] = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ── Provider Discovery ──────────────────────────────────────

    async def _load_config(self) -> Dict[str, Any]:
        """Fetch the OIDC provider's discovery document."""
        if self._config is not None:
            return self._config

        if not self._enabled:
            self._config = {}
            return self._config

        # Build well-known URL
        well_known = self._issuer_url.rstrip("/")
        if not well_known.endswith("/.well-known/openid-configuration"):
            well_known += "/.well-known/openid-configuration"

        async with AsyncClient() as client:
            response = await client.get(well_known, timeout=10)
            response.raise_for_status()
            self._config = response.json()

        logger.info(
            "OIDC provider loaded: %s (issuer: %s)",
            self._config.get("issuer", "unknown"),
            self._issuer_url,
        )
        return self._config

    # ── Auth Flow ───────────────────────────────────────────────

    async def get_login_url(self, request: Request, state: Optional[str] = None) -> str:
        """Generate the OIDC authorization URL.

        Uses signed state parameter for CSRF protection (stored in
        a signed cookie via the ``state`` parameter itself, rather
        than server-side session storage).

        Args:
            request: FastAPI request (used to determine base URL).
            state: Optional state parameter for CSRF protection.

        Returns:
            Full authorization URL to redirect the user to.
        """
        if not self._enabled:
            raise HTTPException(status_code=501, detail="OIDC is not configured")

        config = await self._load_config()
        auth_endpoint = config.get("authorization_endpoint")
        if not auth_endpoint:
            raise HTTPException(status_code=500, detail="OIDC provider missing authorization_endpoint")

        import secrets

        state_value = state or secrets.token_urlsafe(32)

        # Store state securely by passing it through — the callback
        # returns it, so we validate by comparing the returned state
        # to what we sent. Store it as a signed cookie.
        _response_redirect = None  # We'll set this in the calling endpoint

        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "scope": self._scopes,
            "state": state_value,
        }

        return f"{auth_endpoint}?{urlencode(params)}"

    async def handle_callback(
        self, code: str, returned_state: str, expected_state: Optional[str] = None
    ) -> OIDCUserInfo:
        """Handle the OIDC callback (exchange code for tokens).

        This version takes explicit parameters instead of reading from
        ``request.session``, avoiding the need for SessionMiddleware.

        Args:
            code: The authorization code from the OIDC provider.
            returned_state: The state parameter returned by the provider.
            expected_state: The state value we sent (for CSRF validation).

        Returns:
            Normalised user info from the ID token.

        Raises:
            HTTPException: If validation fails.
        """
        if not self._enabled:
            raise HTTPException(status_code=501, detail="OIDC is not configured")

        # Validate state (CSRF protection)
        if expected_state and returned_state != expected_state:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OIDC state mismatch — possible CSRF attack",
            )

        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code",
            )

        config = await self._load_config()
        token_endpoint = config.get("token_endpoint")

        # Exchange code for tokens
        async with AsyncClient() as client:
            token_response = await client.post(
                token_endpoint,  # type: ignore[arg-type]
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._redirect_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )

            if not token_response.is_success:
                logger.error("OIDC token exchange failed: %s", token_response.text)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="OIDC authentication failed",
                )

            token_data = token_response.json()

        id_token = token_data.get("id_token", "")
        if not id_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No ID token received from OIDC provider",
            )

        user_info = self._decode_id_token(id_token, config)
        return user_info

    # ── User Info Extraction ────────────────────────────────────

    def _decode_id_token(self, id_token: str, config: Dict) -> OIDCUserInfo:
        """Decode and extract user info from an OIDC ID token.

        The token is NOT cryptographically verified here (that requires
        the provider's JWKS keys). In production, add JWKS verification.
        """
        import base64

        # Decode JWT payload (second segment)
        parts = id_token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=400, detail="Invalid ID token format")

        # Pad payload for base64 decoding
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        try:
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not decode ID token: {exc}")

        # Detect provider
        issuer = config.get("issuer", payload.get("iss", ""))
        provider = self._detect_provider(issuer)

        # Extract claims with fallbacks
        sub = payload.get("sub", "")
        email = payload.get("email", payload.get("preferred_username", ""))
        name = payload.get("name", payload.get("preferred_username", email))
        username = payload.get("preferred_username", email.split("@")[0] if "@" in email else email)

        # Groups for role mapping
        groups = payload.get("groups", payload.get("roles", []))

        # Check if MFA was performed (via acr/amr claims)
        acr = payload.get("acr", "")
        amr = payload.get("amr", [])
        mfa_performed = (
            "mfa" in amr or "otp" in amr or "phr" in amr or "phrh" in amr or "multifactor" in str(acr).lower()
        )

        return OIDCUserInfo(
            sub=sub,
            email=email,
            username=username,
            name=name,
            provider=provider,
            groups=groups,
            mfa_performed=mfa_performed,
            raw_claims=payload,
        )

    # ── Role Mapping ────────────────────────────────────────────

    async def sync_user(self, user_info: OIDCUserInfo) -> User:
        """Find or create a local user from OIDC user info.

        Maps OIDC groups to local roles. Returns a user with roles
        eagerly loaded so the caller can access them outside the session.

        Args:
            user_info: Normalised OIDC user info.

        Returns:
            Local User ORM object (created or updated).
        """
        from sqlalchemy.orm import joinedload

        with get_session() as session:
            # Find by OIDC subject first, then by email
            user = (
                session.query(User)
                .options(joinedload(User.roles))
                .filter(User.oidc_sub == user_info.sub)
                .first()
            )

            if not user:
                # Try matching by email
                user = (
                    session.query(User)
                    .options(joinedload(User.roles))
                    .filter(User.email == user_info.email)
                    .first()
                )
                if user:
                    user.oidc_sub = user_info.sub  # type: ignore[assignment]
                    user.oidc_provider = user_info.provider  # type: ignore[assignment]
                    user.auth_method = "both"  # type: ignore[assignment]

            if not user:
                # Create new user from OIDC
                default_role = self._map_groups_to_role(user_info.groups, session)

                user = User(
                    username=user_info.username,
                    email=user_info.email,
                    password_hash="OIDC",
                    oidc_sub=user_info.sub,
                    oidc_provider=user_info.provider,
                    auth_method="oidc",
                    is_active=True,
                )
                session.add(user)
                session.flush()

                if default_role:
                    user.roles.append(default_role)
                else:
                    staff_role = session.query(Role).filter(Role.name == RoleName.STAFF.value).first()
                    if staff_role:
                        user.roles.append(staff_role)

            user.last_login_at = User._utcnow()  # type: ignore[attr-defined]
            session.commit()
            session.refresh(user)

            # Eagerly load roles into the user's instance
            _ = user.roles
            return user

    @staticmethod
    def _map_groups_to_role(groups: List[str], session=None) -> Optional[Role]:
        """Map OIDC group memberships to local roles.

        Override this method to customise the mapping for your college.

        Args:
            groups: List of OIDC group names from the ID token.
            session: Optional SQLAlchemy session (uses new one if None).

        Returns:
            The highest-priority matched Role, or None.
        """
        if not groups:
            return None

        if session is None:
            from database.database import get_session

            with get_session() as s:
                return OIDCService._map_groups_to_role(groups, s)

        group_lower = [g.lower() for g in groups]

        # Check in priority order
        role_mapping = [
            (["superadmin", "admin", "system-admin"], RoleName.SUPER_ADMIN),
            (["college-admin", "it-admin", "faculty-admin"], RoleName.COLLEGE_ADMIN),
            (["hod", "head-of-department", "dept-head"], RoleName.HOD),
            (["faculty", "teacher", "lecturer", "professor"], RoleName.FACULTY),
            (["security", "campus-security", "guard"], RoleName.SECURITY),
            (["staff", "employee"], RoleName.STAFF),
            (["student", "pupil"], RoleName.STUDENT),
        ]

        for keywords, role_name in role_mapping:
            if any(kw in g for g in group_lower for kw in keywords):
                role = session.query(Role).filter(Role.name == role_name.value).first()
                if role:
                    return role

        return None

    @staticmethod
    def _detect_provider(issuer: str) -> str:
        """Detect the OIDC provider from the issuer URL."""
        issuer_lower = issuer.lower()

        if "login.microsoftonline.com" in issuer_lower or "sts.windows.net" in issuer_lower:
            return "azure"
        if "keycloak" in issuer_lower:
            return "keycloak"
        if "okta" in issuer_lower:
            return "okta"
        if "accounts.google.com" in issuer_lower:
            return "google"
        if "auth0" in issuer_lower:
            return "auth0"
        return "generic"
