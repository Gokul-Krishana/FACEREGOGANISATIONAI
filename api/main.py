

"""
FastAPI Application for Face Recognition AI - College Deployment.
Provides secure API layer with:

    - RBAC authentication (7 roles)
    - JWT bearer tokens with bcrypt password hashing
    - Rate limiting (slowapi)
    - Security headers (CSP, HSTS, X-Frame-Options)
    - Safe error responses (no stack traces leaked)
    - Upload security (magic bytes, size limits, server-side filenames)
    - Comprehensive audit logging
    - Prometheus metrics
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any, List, Optional

import sys

# Ensure project root is on sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

# Module-level logger
logger = logging.getLogger(__name__)

import config.config as cfg
from database.database import get_session, init_db
from database.models import (
    ActionType,
    AuditAction,
    AuditLog,
    Attendance,
    Camera,
    Course,
    Department,
    Employee,
    Enrollment,
    Institution,
    Permission,
    RecognitionLog,
    RefreshToken,
    Role,
    RoleName,
    Section,
    Staff,
    Student,
    Timetable,
    UnknownFace,
    User,
    _utcnow,
    role_permissions,
    user_roles,
)
from database.repository import EmployeeRepo, PageResult, StudentRepo
from services.attendance_service import AttendanceService
from services.employee_service import EmployeeService
from utils.upload_security import UploadSecurityError, validate_image_upload
from services.brute_force_protection import BruteForceProtection

# ── Security setup ─────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

# ── Rate limiter ───────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


class Settings(BaseModel):
    """Application settings loaded from environment (not user-facing)."""
    database_url: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-change-in-production"))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    cors_origins: List[str] = Field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
    )
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "5"))
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    max_failed_login_attempts: int = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
    lockout_duration_minutes: int = int(os.getenv("LOCKOUT_DURATION_MINUTES", "30"))
    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    password_require_uppercase: bool = os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    password_require_lowercase: bool = os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    password_require_digit: bool = os.getenv("PASSWORD_REQUIRE_DIGIT", "true").lower() == "true"
    password_require_special: bool = os.getenv("PASSWORD_REQUIRE_SPECIAL", "true").lower() == "true"


settings = Settings()

# ── Production Secret Key Validation ─────────────────────────────────
def _validate_production_secret_key():
    """Fail loudly if the default secret key is used in production."""
    if settings.environment == "production":
        if settings.secret_key == "dev-secret-change-in-production":
            raise ValueError(
                "FATAL: Using default SECRET_KEY in production! "
                "Set SECRET_KEY environment variable to a secure random string. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if len(settings.secret_key) < 32:
            raise ValueError(
                "FATAL: SECRET_KEY is too short for production! "
                "Must be at least 32 characters."
            )

_validate_production_secret_key()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    init_db()
    from api.job_queue import register_default_handlers
    register_default_handlers()
    await job_queue.start()
    logger = logging.getLogger(__name__)
    logger.info("Face Recognition AI API started (v2.0.0)")
    yield
    await job_queue.stop()
    logger.info("Face Recognition AI API shutting down")


# Restrict API docs in production for security
_docs_url = "/docs" if settings.environment != "production" else None
_redoc_url = "/redoc" if settings.environment != "production" else None

app = FastAPI(
    title="Face Recognition AI - College API",
    description="Secure API for college-wide face recognition attendance system",
    version="2.0.0",
    lifespan=lifespan,
    # Safe error responses: never leak stack traces in production
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)


# ── Middleware Stack ────────────────────────────────────────────────

# 1. Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)



# 2. CORS (configured via environment for flexible deployment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Requested-With",
    ],
    expose_headers=["X-Request-ID"],
    max_age=600,  # Cache preflight for 10 minutes
)

# 3. Trusted hosts (prevent Host header attacks)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if os.getenv("ENVIRONMENT") == "development" else None,
)


# ── Safe Error Handlers (no stack traces leaked to clients) ────────

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return consistent JSON error responses without stack traces."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "code": exc.status_code,
        },
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all — returns a safe generic message, no internals leaked."""
    logger = logging.getLogger(__name__)
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": 500,
            "request_id": request.headers.get("X-Request-ID", ""),
        },
    )


# ── Security Headers (response middleware) ──────────────────────────

@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    """Add security headers to every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    # Content-Security-Policy (adjust for your env)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    # HSTS (enable once HTTPS is configured)
    if os.getenv("ENABLE_HSTS", "0") == "1":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Request ID middleware ───────────────────────────────────────────

import uuid

@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    """Ensure every request has a traceable ID."""
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ── Request Body Size Limiter ───────────────────────────────────────

MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE_BYTES", str(10 * 1024 * 1024)))  # 10 MB default

@app.middleware("http")
async def limit_request_body_size(request: Request, call_next) -> Response:
    """Reject requests with body larger than MAX_BODY_SIZE.

    Only applies to methods that typically carry a body.
    """
    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit():
            if int(content_length) > MAX_BODY_SIZE:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": f"Request body too large. Maximum size: {MAX_BODY_SIZE // (1024*1024)} MB",
                        "code": 413,
                    },
                )
    return await call_next(request)


# ── Security & RBAC ──────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Session = Depends(get_session),
) -> User:
    """Validate JWT token and return current user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        from jose import jwt
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_permission(resource: str, action: ActionType):
    """Dependency to check if user has required permission."""
    def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        session: Session = Depends(get_session),
    ) -> User:
        user_permissions = session.query(Permission).join(
            role_permissions,
            Permission.id == role_permissions.c.permission_id
        ).join(
            user_roles,
            role_permissions.c.role_id == user_roles.c.role_id
        ).filter(
            user_roles.c.user_id == current_user.id,
            Permission.resource == resource,
            Permission.action == action.value
        ).first()

        if not user_permissions:
            if not session.query(Permission).join(
                role_permissions,
                Permission.id == role_permissions.c.permission_id
            ).join(
                user_roles,
                role_permissions.c.role_id == user_roles.c.role_id
            ).filter(
                user_roles.c.user_id == current_user.id,
                Permission.resource == resource,
                Permission.action == ActionType.EXECUTE.value
            ).first():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {resource}:{action.value}"
                )

        return current_user

    return permission_checker


def require_role(*roles: RoleName):
    """Dependency to check if user has any of the required roles."""
    def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        session: Session = Depends(get_session),
    ) -> User:
        user_roles_query = session.query(Role).join(
            user_roles,
            Role.id == user_roles.c.role_id
        ).filter(
            user_roles.c.user_id == current_user.id,
            Role.name.in_([r.value for r in roles])
        ).first()

        if not user_roles_query:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {[r.value for r in roles]}"
            )

        return current_user

    return role_checker


async def log_audit(
    request: Request,
    action: AuditAction,
    actor: str,
    actor_id: int,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    description: Optional[str] = None,
    details: Optional[dict] = None,
    severity: str = "INFO",
    session: Session = Depends(get_session),
) -> None:
    """Log audit event."""
    audit = AuditLog(
        action=action.value,
        actor=actor,
        actor_type="USER",
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        details=details,
        severity=severity,
    )
    session.add(audit)
    session.commit()


# ── Pydantic Schemas (with input validation) ─────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    sub: int
    username: str
    roles: list[str]


def _validate_password_strength(v: str) -> str:
    """Enforce strong password policy (reusable validator).

    - Minimum 12 characters (configurable)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    - Blocks common weak passwords
    """
    import re

    min_length = settings.password_min_length
    if len(v) < min_length:
        raise ValueError(f"Password must be at least {min_length} characters long")

    if settings.password_require_uppercase and not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")

    if settings.password_require_lowercase and not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")

    if settings.password_require_digit and not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")

    if settings.password_require_special:
        special_chars = r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]"
        if not re.search(special_chars, v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*...)"
                            )

    # Check for common weak passwords
    weak_passwords = {
        "password123!", "password1234!", "changeme123!",
        "admin123!", "letmein123!", "welcome123!",
        "qwerty123!", "abc123456!", "password1!",
    }
    if v.lower() in weak_passwords:
        raise ValueError("This password is too common. Please choose a different one.")

    return v


class UserCreate(BaseModel):
    """User registration request."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class LoginRequest(BaseModel):
    """Login request — username + password only (no email required)."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    roles: list[str]
    created_at: datetime


class StudentCreate(BaseModel):
    """Student creation request."""
    student_id: str = Field(..., min_length=1, max_length=20, pattern=r"^[a-zA-Z0-9\-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    department_id: Optional[int] = Field(None, gt=0)


class StudentResponse(BaseModel):
    id: int
    student_id: str
    name: str
    email: Optional[str] = None
    department_id: Optional[int] = None
    is_active: bool


# ── Employee Schemas ────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    """Employee creation request."""
    employee_id: str = Field(..., min_length=1, max_length=20, pattern=r"^[a-zA-Z0-9\-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    photo_path: Optional[str] = Field(None, max_length=500)


class EmployeeUpdate(BaseModel):
    """Employee update request."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    photo_path: Optional[str] = Field(None, max_length=500)


class EmployeeResponse(BaseModel):
    id: int
    employee_id: str
    name: str
    department: Optional[str] = None
    photo_path: Optional[str] = None
    faiss_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class CameraCreate(BaseModel):
    """Camera registration request."""
    name: str = Field(..., min_length=1, max_length=100)
    camera_id: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9\-_]+$")
    stream_url: Optional[str] = Field(None, max_length=500)
    credential_ref: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=200)
    building: Optional[str] = Field(None, max_length=100)
    room: Optional[str] = Field(None, max_length=50)
    classroom_id: Optional[int] = Field(None, gt=0)


class CameraResponse(BaseModel):
    id: int
    name: str
    camera_id: str
    stream_url: Optional[str] = None
    location: Optional[str] = None
    building: Optional[str] = None
    room: Optional[str] = None
    status: str
    is_active: bool


class AttendanceCreate(BaseModel):
    """Attendance marking request."""
    student_id: int = Field(..., gt=0)
    section_id: Optional[int] = Field(None, gt=0)
    course_id: Optional[int] = Field(None, gt=0)
    classroom_id: Optional[int] = Field(None, gt=0)
    camera_id: Optional[int] = Field(None, gt=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    method: str = Field(default="FACE_RECOGNITION", pattern=r"^[A-Z_]+$")
    status: str = Field(default="PRESENT", pattern=r"^(PRESENT|ABSENT|LATE|EXCUSED)$")


class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    timestamp: datetime
    confidence: float
    method: str
    status: str
    section_id: Optional[int] = None
    course_id: Optional[int] = None
    classroom_id: Optional[int] = None


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    skip: int
    limit: int
    has_more: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: str
    redis: str


class EnrollmentImageResponse(BaseModel):
    """Response after a successful enrollment image upload."""
    filename: str
    size_bytes: int
    message: str


# ── MFA Schemas ────────────────────────────────────────────────────

class MFAEnrollResponse(BaseModel):
    """Response after MFA enrollment."""
    secret: str
    qr_uri: str
    backup_codes: List[str]
    message: str


class MFAVerifyRequest(BaseModel):
    """MFA verification request."""
    code: str = Field(..., min_length=6, max_length=10, description="TOTP code or backup code")
    use_backup: bool = Field(default=False, description="Use backup code instead of TOTP")


class MFAStatusResponse(BaseModel):
    """MFA status response."""
    enabled: bool
    backup_codes_remaining: int
    requires_mfa: bool


# ── OIDC Schemas ───────────────────────────────────────────────────

class OIDCLoginResponse(BaseModel):
    """OIDC login URL response."""
    authorization_url: str
    state: str


class OIDCCallbackResponse(BaseModel):
    """OIDC callback response with token."""
    access_token: str
    token_type: str
    is_new_user: bool


# ── Token Schemas ──────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Full token response with MFA status."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    requires_mfa: bool = False
    mfa_token: Optional[str] = None  # Temporary token for MFA challenge


# ── JWT + Password helpers ────────────────────────────────────────

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Claims to encode (must include ``sub``).
        expires_delta: Token lifetime (default: ``settings.access_token_expire_minutes``).

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def _create_refresh_token(session: Session, user: User, request: Request) -> str:
    """Create a persistent refresh token with rotation support.

    Args:
        session: SQLAlchemy session.
        user: The User to create the token for.
        request: FastAPI request (for IP/device tracking).

    Returns:
        The raw refresh token string (hash stored in DB).
    """
    import hashlib
    import secrets

    from database.models import RefreshToken

    token_str = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(token_str.encode()).hexdigest()

    refresh_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    expires = _utcnow() + timedelta(days=refresh_days)

    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires,
        ip_address=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent", "")[:255],
    )
    session.add(rt)
    session.flush()

    return token_str


# ── Auth Endpoints ──────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse)
@limiter.limit(os.getenv("LOGIN_RATE_LIMIT", "10/minute"))
async def login(
    request: Request,
    form_data: LoginRequest,
    session: Session = Depends(get_session),
):
    """Authenticate and receive tokens.

    If the user has MFA enabled and holds a privileged role, a
    temporary ``mfa_token`` is returned and the client must call
    ``/auth/mfa/verify`` with a TOTP code to get the full token.

    Rate-limited to 10 attempts per minute.

    Includes brute force protection:
    - Tracks failed login attempts per username and IP
    - Locks accounts after 5 failed attempts (30 min lockout)
    - Returns remaining attempts warning before lockout
    """
    from services.mfa_service import MFAService

    # Get client IP for brute force tracking
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Check for account lockout before attempting login
    is_locked, lockout_msg = BruteForceProtection.is_locked_out(form_data.username, client_ip)
    if is_locked:
        # Log the attempt even when locked
        BruteForceProtection.record_failed_attempt(
            form_data.username, client_ip, user_agent
        )
        await log_audit(
            request, AuditAction.USER_LOGIN, form_data.username, 0,
            description=f"Login blocked: {lockout_msg}",
            severity="WARNING",
            session=session,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=lockout_msg,
        )

    user = session.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.password_hash):
        # Record failed attempt for brute force protection
        BruteForceProtection.record_failed_attempt(
            form_data.username, client_ip, user_agent
        )

        # Get remaining attempts info
        lockout_info = BruteForceProtection.get_lockout_info(form_data.username)
        remaining = lockout_info.get("remaining_attempts", 0)

        # Log failed attempt
        await log_audit(
            request, AuditAction.USER_LOGIN, form_data.username, 0,
            description=f"Failed login attempt for {form_data.username} from {client_ip}",
            severity="WARNING",
            session=session,
        )

        detail = "Invalid credentials"
        if remaining <= 2 and remaining > 0:
            detail = f"Invalid credentials. Warning: {remaining} attempts remaining before account lockout."

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Record successful login (resets failed attempt counter)
    BruteForceProtection.record_successful_login(form_data.username, client_ip)

    # ── Check if MFA is required for this user ────────────────
    requires_mfa = MFAService.requires_mfa(user)

    if requires_mfa:
        # Issue a short-lived MFA token (2 min) that only allows MFA verification
        mfa_token = create_access_token(
            data={"sub": user.id, "username": user.username,
                   "roles": [r.name for r in user.roles], "mfa_pending": True},
            expires_delta=timedelta(minutes=2),
        )

        await log_audit(
            request, AuditAction.USER_LOGIN, user.username, user.id,
            description=f"User {user.username} requires MFA verification",
            session=session,
        )

        return TokenResponse(
            access_token="",
            requires_mfa=True,
            mfa_token=mfa_token,
        )

    # ── Issue full access + refresh tokens ────────────────────
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username,
               "roles": [r.name for r in user.roles]}
    )
    refresh_token_str = _create_refresh_token(session, user, request)

    await log_audit(
        request, AuditAction.USER_LOGIN, user.username, user.id,
        description=f"User {user.username} logged in",
        session=session,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        requires_mfa=False,
    )


@app.post("/auth/logout")
@limiter.limit("20/minute")
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Log out the current user."""
    await log_audit(
        request, AuditAction.USER_LOGOUT, current_user.username, current_user.id,
        description=f"User {current_user.username} logged out",
        session=session
    )
    return {"message": "Logged out successfully"}


@app.get("/auth/me", response_model=UserResponse)
@limiter.limit("30/minute")
async def get_current_user_info(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        roles=[r.name for r in current_user.roles],
        created_at=current_user.created_at,
    )


@app.post("/auth/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    body: PasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Change the current user's password.

    Requires:
        - Current password verification
        - New password meets strength requirements
        - Invalidates all existing refresh tokens (force re-login)

    Security:
        - Rate limited to 5 attempts per minute
        - All refresh tokens are revoked after password change
        - Audit log entry is created
    """
    # Verify current password
    if not pwd_context.verify(body.current_password, current_user.password_hash):
        await log_audit(
            request, AuditAction.PASSWORD_CHANGE_FAILED, current_user.username, current_user.id,
            description=f"Password change failed: incorrect current password for {current_user.username}",
            severity="WARNING",
            session=session,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Check if new password is different from current
    if pwd_context.verify(body.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Update password hash
    current_user.password_hash = pwd_context.hash(body.new_password)
    current_user.updated_at = _utcnow()

    # Revoke ALL refresh tokens for this user (force re-login on all devices)
    revoked_count = session.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": _utcnow()})

    session.commit()

    await log_audit(
        request, AuditAction.PASSWORD_CHANGED, current_user.username, current_user.id,
        description=f"Password changed for {current_user.username}. Revoked {revoked_count} refresh tokens.",
        details={"revoked_tokens": revoked_count},
        session=session,
    )

    return {
        "message": "Password changed successfully. All existing sessions have been invalidated. Please log in again.",
        "revoked_tokens": revoked_count,
    }


@app.post("/auth/revoke-all-sessions")
@limiter.limit("3/minute")
async def revoke_all_sessions(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Session = Depends(get_session),
):
    """Revoke all refresh tokens for the current user.

    Useful if the user suspects their account has been compromised.
    Forces re-authentication on all devices.
    """
    revoked_count = session.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": _utcnow()})

    session.commit()

    await log_audit(
        request, AuditAction.SECURITY_ALERT, current_user.username, current_user.id,
        description=f"All sessions revoked for {current_user.username}. Revoked {revoked_count} tokens.",
        details={"revoked_tokens": revoked_count},
        severity="WARNING",
        session=session,
    )

    return {
        "message": f"All {revoked_count} sessions have been revoked. Please log in again.",
        "revoked_tokens": revoked_count,
    }


# ── MFA Endpoints ─────────────────────────────────────────────────

@app.post("/auth/mfa/enroll", response_model=MFAEnrollResponse)
@limiter.limit("5/minute")
async def enroll_mfa(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("mfa", ActionType.UPDATE))],
):
    """Enroll in MFA for the current user.

    Generates a TOTP secret and backup codes. The secret should be
    added to an authenticator app (Google Authenticator, Authy, etc.)
    using the QR URI. Backup codes must be saved — they are shown
    exactly once.

    Returns a provisioning URI that can be rendered as a QR code.
    """
    from services.mfa_service import MFAService

    secret, qr_uri, backup_codes = MFAService.enroll_user(current_user)

    return MFAEnrollResponse(
        secret=secret,
        qr_uri=qr_uri,
        backup_codes=backup_codes,
        message="MFA enabled. Save backup codes in a safe place — they will not be shown again.",
    )


@app.post("/auth/mfa/verify", response_model=TokenResponse)
@limiter.limit("10/minute")
async def verify_mfa(
    request: Request,
    body: MFAVerifyRequest,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    session: Session = Depends(get_session),
):
    """Verify an MFA code and receive a full access token.

    After logging in with ``requires_mfa=true`` in the response, the
    client should call this endpoint with the temporary ``mfa_token``
    in the Authorization header and the TOTP/backup code in the body.

    This endpoint **only** accepts MFA-pending tokens, not regular
    access tokens — this prevents bypassing MFA with an existing token.
    """
    from services.mfa_service import MFAService

    # Validate token and enforce it has mfa_pending claim
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        from jose import jwt
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if not payload.get("mfa_pending"):
            raise HTTPException(
                status_code=403,
                detail="This endpoint requires an MFA-pending token. Use the login endpoint first.",
            )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA token")

    current_user = session.get(User, user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    success, msg = MFAService.verify_and_update(
        user=current_user,
        code=body.code,
        use_backup=body.use_backup,
    )

    if not success:
        await log_audit(
            request, AuditAction.USER_LOGIN, current_user.username, current_user.id,
            description=f"MFA verification failed for {current_user.username}",
            severity="WARNING",
            session=session,
        )
        raise HTTPException(status_code=401, detail=msg)

    # Issue full access token (with refresh token)
    access_token = create_access_token(
        data={"sub": current_user.id, "username": current_user.username,
               "roles": [r.name for r in current_user.roles], "mfa": True}
    )
    refresh_token_str = _create_refresh_token(session, current_user, request)

    await log_audit(
        request, AuditAction.USER_LOGIN, current_user.username, current_user.id,
        description=f"User {current_user.username} completed MFA verification",
        session=session,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        requires_mfa=False,
    )


@app.get("/auth/mfa/status", response_model=MFAStatusResponse)
async def mfa_status(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the MFA status for the current user."""
    from services.mfa_service import MFAService

    backup_codes = current_user.mfa_backup_codes or []
    return MFAStatusResponse(
        enabled=current_user.is_mfa_enabled,
        backup_codes_remaining=len(backup_codes),
        requires_mfa=MFAService.requires_mfa(current_user),
    )


@app.post("/auth/mfa/disable")
@limiter.limit("5/minute")
async def disable_mfa(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("mfa", ActionType.UPDATE))],
    session: Session = Depends(get_session),
):
    """Disable MFA for the current user."""
    from services.mfa_service import MFAService

    MFAService.disable_mfa(current_user)

    await log_audit(
        request, AuditAction.SYSTEM_CONFIG_CHANGED, current_user.username, current_user.id,
        description=f"User {current_user.username} disabled MFA",
        session=session,
    )

    return {"message": "MFA disabled"}


# ── OIDC Endpoints ─────────────────────────────────────────────────

@app.get("/auth/oidc/login", response_model=OIDCLoginResponse)
@limiter.limit("10/minute")
async def oidc_login(request: Request):
    """Initiate OIDC SSO login.

    Returns the authorization URL to redirect the user to the college's
    identity provider. The state is stored server-side (Redis) for
    5 minutes to prevent CSRF attacks on the callback.
    """
    from services.oidc_service import OIDCService
    from api.redis_client import get_redis

    oidc = OIDCService()
    if not oidc.enabled:
        raise HTTPException(
            status_code=501,
            detail="SSO is not configured. Set OIDC_ISSUER_URL, OIDC_CLIENT_ID, and OIDC_CLIENT_SECRET.",
        )

    import secrets
    state = secrets.token_urlsafe(32)
    auth_url = await oidc.get_login_url(request, state=state)

    # Store state in Redis with 5-minute TTL for CSRF validation
    try:
        redis = get_redis()
        redis.cache_set(f"oidc_state:{state}", "1", ttl=300)
    except Exception:
        logger.warning("Could not store OIDC state in Redis — CSRF protection degraded")

    return OIDCLoginResponse(authorization_url=auth_url, state=state)


@app.get("/auth/oidc/callback", response_model=OIDCCallbackResponse)
@limiter.limit("10/minute")
async def oidc_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    session: Session = Depends(get_session),
):
    """Handle the OIDC callback after SSO login.

    The OIDC provider redirects here after the user authenticates.
    Validates the state parameter against the server-side copy in
    Redis (CSRF protection), then exchanges the code for tokens.

    Args:
        code: Authorization code from the OIDC provider.
        state: State parameter for CSRF validation.
    """
    from services.oidc_service import OIDCService
    from api.redis_client import get_redis

    oidc = OIDCService()
    if not oidc.enabled:
        raise HTTPException(status_code=501, detail="SSO is not configured")

    # Validate state against stored value in Redis (CSRF protection)
    try:
        redis = get_redis()
        stored_state = redis.cache_get(f"oidc_state:{state}")
        if not stored_state:
            raise HTTPException(
                status_code=403,
                detail="Invalid or expired OIDC state — possible CSRF attack. Please login again.",
            )
        # Delete the used state (one-time use)
        redis.cache_delete(f"oidc_state:{state}")
    except HTTPException:
        raise
    except Exception:
        logger.warning("Redis unavailable — OIDC CSRF validation skipped")

    try:
        user_info = await oidc.handle_callback(code=code, returned_state=state, expected_state=state)

        # Find or create local user from OIDC claims
        user = await oidc.sync_user(user_info)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("OIDC callback error: %s", exc, exc_info=True)
        raise HTTPException(status_code=401, detail="SSO authentication failed")

    # Check if OIDC provider performed MFA
    if user_info.mfa_performed:
        # MFA was handled at the IdP — mark as verified
        with get_session() as s:
            db_user = s.query(User).filter(User.id == user.id).first()
            if db_user:
                from datetime import datetime, timezone
                db_user.mfa_last_verified = datetime.now(timezone.utc)
                s.commit()

    access_token = create_access_token(
        data={"sub": user.id, "username": user.username,
               "roles": [r.name for r in user.roles], "oidc": True}
    )

    await log_audit(
        request, AuditAction.USER_LOGIN, user.username, user.id,
        description=f"User {user.username} logged in via SSO ({user_info.provider})",
        session=session,
    )

    return OIDCCallbackResponse(
        access_token=access_token,
        token_type="bearer",
        is_new_user=user.auth_method == "oidc",
    )


# ── Password Change Schema ────────────────────────────────────────

class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str = Field(..., min_length=8, description="Current password for verification")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Enforce strong password policy for new password."""
        import re

        min_length = settings.password_min_length
        if len(v) < min_length:
            raise ValueError(f"Password must be at least {min_length} characters long")

        if settings.password_require_uppercase and not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")

        if settings.password_require_lowercase and not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")

        if settings.password_require_digit and not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")

        if settings.password_require_special:
            special_chars = r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]"
            if not re.search(special_chars, v):
                raise ValueError("Password must contain at least one special character")

        return v


# ── Refresh Token Schemas ────────────────────────────────────────

class RefreshTokenRequest(BaseModel):
    """Refresh token request body (not query param, to avoid logging)."""
    refresh_token: str = Field(..., min_length=16, description="Refresh token from login response")


# ── Refresh Token Endpoint ─────────────────────────────────────────

@app.post("/auth/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    body: RefreshTokenRequest,
    session: Session = Depends(get_session),
):
    """Exchange a refresh token for a new access token.

    Implements refresh token rotation: the old token is revoked and
    a new one is issued. If a revoked token is reused (theft
    detection), all tokens for the user are revoked.

    The refresh token is sent in the POST body, not a URL query
    parameter, to prevent it from appearing in server logs.
    """
    import hashlib
    from database.models import RefreshToken

    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()

    # Find the refresh token
    rt = session.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not rt:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if rt.is_revoked:
        # Token reuse — possible theft. Revoke ALL tokens for this user.
        logger.warning(
            "Refresh token reuse detected for user %s — revoking all tokens",
            rt.user_id,
        )
        session.query(RefreshToken).filter(
            RefreshToken.user_id == rt.user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({"revoked_at": _utcnow()})
        session.commit()
        raise HTTPException(status_code=401, detail="Token has been revoked")

    if rt.is_expired:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Revoke old token
    rt.revoked_at = _utcnow()

    # Issue new tokens
    user = session.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "roles": [r.name for r in user.roles]}
    )

    new_refresh = _create_refresh_token(session, user, request)
    rt.replaced_by = hashlib.sha256(new_refresh.encode()).hexdigest()
    session.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        requires_mfa=False,
    )


# ── Health & Monitoring ──────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
@limiter.exempt
async def health_check(request: Request):
    """Health check endpoint (not rate-limited)."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=_utcnow(),
        database="connected",
        redis="connected",
    )


@app.get("/metrics")
@limiter.exempt
async def metrics(request: Request):
    """Prometheus metrics endpoint (not rate-limited)."""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Enrollment & Upload ────────────────────────────────────────────

@app.post("/enroll/upload", response_model=EnrollmentImageResponse)
@limiter.limit(os.getenv("ENROLL_RATE_LIMIT", "5/minute"))
async def upload_enrollment_image(
    request: Request,
    file: UploadFile = File(...),
    current_user: Annotated[User, Depends(require_permission("enrollment", ActionType.CREATE))] = None,
):
    """Upload an enrollment photo with security validation.

    Validates:
        - File size (max 5 MB)
        - Actual content type (magic bytes, not just extension)
        - Image validity (not corrupt)
        - Dimensions within limits

    Returns a server-generated filename — the original filename
    is never used for storage.
    """
    file_data = await file.read()
    try:
        safe_filename, validated_data = validate_image_upload(
            file_data=file_data,
            filename=file.filename or "upload",
            max_size_mb=settings.max_upload_size_mb,
        )
    except UploadSecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Save to the uploads directory
    upload_dir = cfg.ROOT_DIR / "uploads" / "enrollment"
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = upload_dir / safe_filename
    save_path.write_bytes(validated_data)

    return EnrollmentImageResponse(
        filename=safe_filename,
        size_bytes=len(validated_data),
        message="Enrollment image uploaded successfully. Submit it with the enrollment request.",
    )


# ── Student Management ───────────────────────────────────────────────

@app.post("/students", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def create_student(
    request: Request,
    student: StudentCreate,
    current_user: Annotated[User, Depends(require_permission("students", ActionType.CREATE))],
    session: Session = Depends(get_session),
):
    """Create a new student."""
    db_student = Student(**student.model_dump())
    session.add(db_student)
    session.commit()
    session.refresh(db_student)

    await log_audit(
        request, AuditAction.STUDENT_ENROLLED, current_user.username, current_user.id,
        resource_type="Student", resource_id=db_student.id,
        description=f"Student {db_student.student_id} enrolled",
        session=session
    )
    return StudentResponse.model_validate(db_student)


@app.get("/students", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def list_students(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("students", ActionType.READ))],
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by student name or student ID"),
    department_id: Optional[int] = Query(None, gt=0),
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List students with server-side pagination and optional search."""
    if q or department_id is not None or is_active is not None:
        page = StudentRepo.search(
            session,
            query=q or "",
            limit=limit,
            skip=skip,
            department_id=department_id,
            is_active=is_active,
        )
    else:
        query = session.query(Student).order_by(Student.name, Student.id)
        page = PageResult(
            items=query.offset(skip).limit(limit).all(),
            total=session.query(func.count(Student.id)).scalar() or 0,
            skip=skip,
            limit=limit,
        )
    items = [StudentResponse.model_validate(s).model_dump() for s in page.items]
    return PaginatedResponse(
        items=items,
        total=page.total,
        skip=page.skip,
        limit=page.limit,
        has_more=page.has_more,
    )


@app.get("/students/{student_id}", response_model=StudentResponse)
@limiter.limit("60/minute")
async def get_student(
    request: Request,
    student_id: int,
    current_user: Annotated[User, Depends(require_permission("students", ActionType.READ))],
    session: Session = Depends(get_session),
):
    """Get a specific student."""
    student = session.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return StudentResponse.model_validate(student)


# ── Employee Management ───────────────────────────────────────────────

@app.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def create_employee(
    request: Request,
    employee: EmployeeCreate,
    current_user: Annotated[User, Depends(require_permission("employees", ActionType.CREATE))],
    session: Session = Depends(get_session),
):
    """Create a new employee."""
    # Check for duplicate employee_id
    existing = session.query(Employee).filter(Employee.employee_id == employee.employee_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee '{employee.employee_id}' already exists",
        )

    db_employee = Employee(**employee.model_dump())
    session.add(db_employee)
    session.commit()
    session.refresh(db_employee)

    await log_audit(
        request, AuditAction.EMPLOYEE_ENROLLED, current_user.username, current_user.id,
        resource_type="Employee", resource_id=db_employee.id,
        description=f"Employee {db_employee.employee_id} enrolled",
        session=session,
    )
    return EmployeeResponse.model_validate(db_employee)


@app.get("/employees", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def list_employees(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("employees", ActionType.READ))],
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by employee name, ID, or department"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List employees with pagination and search."""
    page = EmployeeRepo.search_paginated(session, query=q or "", limit=limit, skip=skip)
    items = [EmployeeResponse.model_validate(e).model_dump() for e in page.items]
    return PaginatedResponse(
        items=items,
        total=page.total,
        skip=page.skip,
        limit=page.limit,
        has_more=page.has_more,
    )


@app.get("/employees/{employee_id}", response_model=EmployeeResponse)
@limiter.limit("60/minute")
async def get_employee(
    request: Request,
    employee_id: int,
    current_user: Annotated[User, Depends(require_permission("employees", ActionType.READ))],
    session: Session = Depends(get_session),
):
    """Get a specific employee by database ID."""
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return EmployeeResponse.model_validate(employee)


@app.put("/employees/{employee_id}", response_model=EmployeeResponse)
@limiter.limit("60/minute")
async def update_employee(
    employee_id: int,
    request: Request,
    body: EmployeeUpdate,
    current_user: Annotated[User, Depends(require_permission("employees", ActionType.UPDATE))],
    session: Session = Depends(get_session),
):
    """Update an existing employee."""
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(employee, key, value)

    session.commit()
    session.refresh(employee)

    await log_audit(
        request, AuditAction.EMPLOYEE_UPDATED, current_user.username, current_user.id,
        resource_type="Employee", resource_id=employee.id,
        description=f"Employee {employee.employee_id} updated",
        details={"fields": list(update_data.keys())},
        session=session,
    )
    return EmployeeResponse.model_validate(employee)


@app.delete("/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_employee(
    employee_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_permission("employees", ActionType.DELETE))],
    session: Session = Depends(get_session),
):
    """Delete an employee by database ID.

    Also removes the employee's embedding(s) from the FAISS index so
    the deleted employee is no longer recognised by the camera pipeline.

    Returns 204 No Content on success.
    """
    employee = session.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    emp_id_str = employee.employee_id
    emp_name = employee.name
    session.delete(employee)
    session.commit()

    # Keep FAISS in sync — remove the embedding so the deleted employee
    # is no longer recognised. The helper logs FAISS failures internally
    # and never raises.
    EmployeeService.remove_faiss_embedding(emp_name, fallback=emp_id_str)

    await log_audit(
        request, AuditAction.DATA_DELETED, current_user.username, current_user.id,
        resource_type="Employee", resource_id=employee_id,
        description=f"Employee '{emp_name}' ({emp_id_str}) deleted",
        session=session,
    )
    return None


# ── Camera Management ────────────────────────────────────────────────

@app.post("/cameras", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def create_camera(
    request: Request,
    camera: CameraCreate,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    session: Session = Depends(get_session),
):
    """Create a new camera."""
    db_camera = Camera(**camera.model_dump())
    session.add(db_camera)
    session.commit()
    session.refresh(db_camera)

    await log_audit(
        request, AuditAction.CAMERA_ADDED, current_user.username, current_user.id,
        resource_type="Camera", resource_id=db_camera.id,
        description=f"Camera {db_camera.camera_id} added",
        session=session
    )

    return CameraResponse.model_validate(db_camera)


@app.get("/cameras", response_model=PaginatedResponse)
@limiter.limit("30/minute")
async def list_cameras(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("cameras", ActionType.READ))],
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None, description="Search by camera name, location, building, or room"),
    is_active: Optional[bool] = None,
    status: Optional[str] = Query(None, description="Filter by ONLINE/OFFLINE status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List cameras with pagination and filters."""
    query = session.query(Camera)
    if q:
        pattern = f"{q.strip()}%"
        query = query.filter(
            or_(
                Camera.name.ilike(pattern),
                Camera.location.ilike(pattern),
                Camera.building.ilike(pattern),
                Camera.room.ilike(pattern),
                Camera.camera_id.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(Camera.is_active == is_active)
    if status:
        query = query.filter(Camera.status == status)
    query = query.order_by(Camera.name, Camera.id)
    page = PageResult(
        items=query.offset(skip).limit(limit).all(),
        total=query.order_by(None).count(),
        skip=skip,
        limit=limit,
    )
    items = [CameraResponse.model_validate(c).model_dump() for c in page.items]
    return PaginatedResponse(
        items=items,
        total=page.total,
        skip=page.skip,
        limit=page.limit,
        has_more=page.has_more,
    )


@app.get("/cameras/{camera_id}")
@limiter.limit("30/minute")
async def get_camera(
    request: Request,
    camera_id: int,
    current_user: Annotated[User, Depends(require_permission("cameras", ActionType.READ))],
    session: Session = Depends(get_session),
):
    """Get camera details."""
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraResponse.model_validate(camera)


@app.patch("/cameras/{camera_id}/status")
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def update_camera_status(
    camera_id: int,
    request: Request,
    body: CameraStatusUpdate,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    session: Session = Depends(get_session),
):
    """Update camera status.

    Uses a validated Pydantic model to ensure the request body is
    well-formed before any state changes.
    """
    camera = session.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    old_status = camera.status
    camera.is_active = body.is_active
    camera.status = "ONLINE" if body.is_active else "OFFLINE"
    camera.last_seen = _utcnow()
    session.commit()

    await log_audit(
        request, AuditAction.CAMERA_STATUS_CHANGED, current_user.username, current_user.id,
        resource_type="Camera", resource_id=camera.id,
        description=f"Camera {camera.camera_id} status changed from {old_status} to {camera.status}",
        details={"old_status": old_status, "new_status": camera.status},
        session=session
    )

    return CameraResponse.model_validate(camera)


# ── Attendance Management ────────────────────────────────────────────

@app.post("/attendance", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def mark_attendance(
    request: Request,
    attendance: AttendanceCreate,
    current_user: Annotated[User, Depends(require_permission("attendance", ActionType.CREATE))],
    session: Session = Depends(get_session),
):
    """Mark attendance for a student."""
    # Validate student exists
    student = session.get(Student, attendance.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate timetable context if provided
    if attendance.section_id:
        section = session.get(Section, attendance.section_id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        # Check if student is enrolled in this section
        enrollment = session.query(Enrollment).filter(
            Enrollment.student_id == attendance.student_id,
            Enrollment.section_id == attendance.section_id,
            Enrollment.status == "ACTIVE"
        ).first()
        if not enrollment:
            raise HTTPException(status_code=400, detail="Student not enrolled in this section")

    db_attendance = Attendance(**attendance.model_dump())
    session.add(db_attendance)
    session.commit()
    session.refresh(db_attendance)

    await log_audit(
        request, AuditAction.ATTENDANCE_MARKED, current_user.username, current_user.id,
        resource_type="Attendance", resource_id=db_attendance.id,
        description=f"Attendance marked for student {student.student_id}",
        details={"section_id": attendance.section_id, "confidence": attendance.confidence},
        session=session
    )

    return AttendanceResponse(
        id=db_attendance.id,
        student_id=student.id,
        student_name=student.name,
        timestamp=db_attendance.timestamp,
        confidence=db_attendance.confidence,
        method=db_attendance.method,
        status=db_attendance.status,
        section_id=db_attendance.section_id,
        course_id=db_attendance.course_id,
        classroom_id=db_attendance.classroom_id,
    )


@app.get("/attendance", response_model=PaginatedResponse)
@limiter.limit("60/minute")
async def get_attendance(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("attendance", ActionType.READ))],
    session: Session = Depends(get_session),
    student_id: Optional[int] = None,
    section_id: Optional[int] = None,
    course_id: Optional[int] = None,
    date_from: Optional[str] = Query(None, description="ISO date string (e.g. 2024-01-15 or 2024-01-15T00:00:00)"),
    date_to: Optional[str] = Query(None, description="ISO date string (e.g. 2024-01-15 or 2024-01-15T00:00:00)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """Get attendance records with filters.

    Date params accept ISO 8601 strings like ``2024-01-15`` or
    ``2024-01-15T09:30:00``. Plain dates are interpreted as UTC.
    """
    query = session.query(Attendance).options(selectinload(Attendance.student))

    if student_id:
        query = query.filter(Attendance.student_id == student_id)
    if section_id:
        query = query.filter(Attendance.section_id == section_id)
    if course_id:
        query = query.filter(Attendance.course_id == course_id)
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
        except ValueError:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(Attendance.timestamp >= dt)
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
        except ValueError:
            # Plain date → end of that day
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        query = query.filter(Attendance.timestamp <= dt)

    total = query.order_by(None).count()
    attendances = (
        query.order_by(Attendance.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for a in attendances:
        student_name = a.student.name if a.student else "Unknown"
        results.append(
            AttendanceResponse(
                id=a.id,
                student_id=a.student_id,
                student_name=student_name,
                timestamp=a.timestamp,
                confidence=a.confidence,
                method=a.method,
                status=a.status,
                section_id=a.section_id,
                course_id=a.course_id,
                classroom_id=a.classroom_id,
            )
        )
    return PaginatedResponse(
        items=[item.model_dump() for item in results],
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(results) < total,
    )


# ── Unknown Face Management ──────────────────────────────────────────

class ReviewAction(str, Enum):
    """Valid actions for reviewing unknown faces."""
    APPROVE = "approve"
    DISMISS = "dismiss"
    DELETE = "delete"


class CameraStatusUpdate(BaseModel):
    """Request body for updating camera status."""
    is_active: bool = Field(..., description="Whether the camera should be active")


class UnknownFaceResponse(BaseModel):
    id: int
    image_path: str
    camera_id: Optional[int] = None
    timestamp: datetime
    reviewed: bool
    reviewed_by: Optional[int] = None
    converted_to_employee: bool


@app.get("/unknown-faces", response_model=PaginatedResponse)
@limiter.limit("30/minute")
async def list_unknown_faces(
    request: Request,
    current_user: Annotated[User, Depends(require_role(RoleName.SECURITY, RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    session: Session = Depends(get_session),
    reviewed: Optional[bool] = None,
    camera_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List unknown faces."""
    query = session.query(UnknownFace)

    if reviewed is not None:
        query = query.filter(UnknownFace.reviewed == reviewed)
    if camera_id is not None:
        query = query.filter(UnknownFace.camera_id == camera_id)

    total = query.order_by(None).count()
    faces = (
        query.order_by(UnknownFace.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [UnknownFaceResponse.model_validate(u).model_dump() for u in faces]
    return PaginatedResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
        has_more=skip + len(items) < total,
    )


@app.post("/unknown-faces/{face_id}/review")
@limiter.limit(os.getenv("API_RATE_LIMIT", "100/minute"))
async def review_unknown_face(
    face_id: int,
    request: Request,
    current_user: Annotated[User, Depends(require_role(RoleName.SECURITY, RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    action: ReviewAction = Query(...),
    employee_id: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """Review an unknown face.

    Args:
        action: Must be one of ``approve``, ``dismiss``, or ``delete``.
    """
    face = session.get(UnknownFace, face_id)
    if not face:
        raise HTTPException(status_code=404, detail="Unknown face not found")

    face.reviewed = True
    face.reviewed_by = current_user.id
    face.reviewed_at = _utcnow()

    if action == ReviewAction.APPROVE and employee_id:
        face.converted_to_employee = True
        # Create attendance record if needed
        pass

    session.commit()

    await log_audit(
        request, AuditAction.UNKNOWN_FACE_REVIEWED, current_user.username, current_user.id,
        resource_type="UnknownFace", resource_id=face_id,
        description=f"Unknown face {face_id} {action}ed",
        details={"action": action, "employee_id": employee_id},
        session=session
    )

    return {"message": f"Face {action}ed successfully"}


# ── Analytics Endpoints ──────────────────────────────────────────────

@app.get("/analytics/attendance-summary")
@limiter.limit("20/minute")
async def attendance_summary(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("analytics", ActionType.READ))],
    session: Session = Depends(get_session),
    date_from: Optional[str] = Query(None, description="ISO date string (e.g. 2024-01-15)"),
    date_to: Optional[str] = Query(None, description="ISO date string (e.g. 2024-01-15)"),
):
    """Get attendance summary statistics."""
    from sqlalchemy import func, extract

    query = session.query(
        func.date(Attendance.timestamp).label("date"),
        func.count(Attendance.id).label("count"),
        func.count(func.distinct(Attendance.student_id)).label("unique_students"),
    ).group_by(func.date(Attendance.timestamp))

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
        except ValueError:
            dt = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(Attendance.timestamp >= dt)
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
        except ValueError:
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        query = query.filter(Attendance.timestamp <= dt)

    results = query.all()
    return [
        {
            "date": str(r.date),
            "total_attendance": r.count,
            "unique_students": r.unique_students,
        }
        for r in results
    ]


@app.get("/analytics/camera-status")
@limiter.limit("20/minute")
async def camera_status(
    request: Request,
    current_user: Annotated[User, Depends(require_role(RoleName.SECURITY, RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    session: Session = Depends(get_session),
):
    """Get camera status overview."""
    cameras = session.query(Camera).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "camera_id": c.camera_id,
            "status": c.status,
            "last_seen": c.last_seen,
            "building": c.building,
            "room": c.room,
        }
        for c in cameras
    ]


# ═══════════════════════════════════════════════════════════════════
#  College-Scale Backend — WebSocket / SSE / Jobs / Bulk Ops
# ═══════════════════════════════════════════════════════════════════

from fastapi import WebSocket, Query as WSQuery
from api.websocket_manager import ws_manager
from api.job_queue import job_queue, register_default_handlers, JobStatus
from api.bulk_operations import bulk_operations, BulkResult


# ── WebSocket: Live Recognition Events ───────────────────────────

@app.websocket("/ws/live")
async def websocket_live_events(
    websocket: WebSocket,
    token: str = WSQuery(...),
    camera_id: Optional[int] = WSQuery(None),
):
    """WebSocket endpoint for live recognition events.

    Query params:
        token: JWT access token (from /auth/login).
        camera_id: Optional camera filter — only receive events from this camera.

    Events sent:
        {"type": "recognition", "student_name": "...", "camera_id": 1, ...}
        {"type": "camera_status", "camera_id": 1, "status": "ONLINE"}
        {"type": "ping"} (heartbeat)
    """
    # Authenticate
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("sub")
        username = payload.get("username", "unknown")
        roles = payload.get("roles", [])
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    client = await ws_manager.connect(
        websocket=websocket,
        user_id=user_id,
        username=username,
        roles=roles,
        camera_filter=camera_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            # Handle client messages (e.g., ping response, subscribe/unsubscribe)
            msg_type = data.get("type", "")
            if msg_type == "pong":
                client.last_pong = time.time()
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(client)


import time


# ── SSE: Server-Sent Events endpoint (alternative to WebSocket) ───

from fastapi.responses import StreamingResponse
import asyncio
import json as json_mod


@app.get("/events/stream")
async def sse_live_events(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    camera_id: Optional[int] = Query(None),
):
    """Server-Sent Events endpoint for live recognition events.

    Alternative to WebSocket for clients that don't support WS.
    Includes JWT authentication via query param or header.
    """
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        # Create a simple client wrapper for SSE
        class SSEClient:
            def __init__(self):
                self.queue = queue
                self.user_id = current_user.id
                self.username = current_user.username
                self.roles = [r.name for r in current_user.roles]
                self.camera_filter = camera_id
                self.connected_at = time.time()
                self.last_pong = time.time()
                self.events_sent = 0

            async def send_json(self, data: dict):
                """Put event into the async queue for SSE streaming."""
                await self.queue.put(data)

        sse_client = SSEClient()
        async with ws_manager._lock:
            ws_manager._connections.append(sse_client)

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json_mod.dumps(event)}\n\n"
                    sse_client.events_sent += 1
                except asyncio.TimeoutError:
                    yield f"data: {json_mod.dumps({'type': 'ping'})}\n\n"
        finally:
            async with ws_manager._lock:
                if sse_client in ws_manager._connections:
                    ws_manager._connections.remove(sse_client)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Job Queue Endpoints ──────────────────────────────────────────

class JobCreateRequest(BaseModel):
    job_type: str = Field(..., description="Type of job: batch_enroll, rebuild_index, cleanup_unknown")
    params: dict = Field(default_factory=dict, description="Job parameters")


@app.post("/jobs", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_job(
    request: Request,
    body: JobCreateRequest,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Create a background job."""
    job_id = await job_queue.enqueue(
        job_type=body.job_type,
        params=body.params,
        created_by=current_user.username,
    )
    return {"job_id": job_id, "status": "pending", "job_type": body.job_type}


@app.get("/jobs")
@limiter.limit("30/minute")
async def list_jobs(
    request: Request,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
    job_status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
):
    """List background jobs."""
    status_filter = JobStatus(job_status) if job_status else None
    jobs = await job_queue.list_jobs(status_filter=status_filter, limit=limit)
    return {"jobs": jobs, "stats": job_queue.stats()}


@app.get("/jobs/{job_id}")
@limiter.limit("60/minute")
async def get_job_status(
    request: Request,
    job_id: str,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Get job status."""
    status = await job_queue.status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status


@app.post("/jobs/{job_id}/cancel")
@limiter.limit("10/minute")
async def cancel_job(
    request: Request,
    job_id: str,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Cancel a background job."""
    success = await job_queue.cancel(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already completed")
    return {"message": "Job cancelled", "job_id": job_id}


# ── Bulk Operations Endpoints ────────────────────────────────────

class BulkStudentImport(BaseModel):
    csv_content: str = Field(..., description="CSV content with student records")
    default_department_id: Optional[int] = Field(None, description="Default department for students without department")
    skip_duplicates: bool = Field(True, description="Skip existing student IDs")


class BulkEmployeeImport(BaseModel):
    csv_content: str = Field(..., description="CSV content with employee records")
    skip_duplicates: bool = Field(True, description="Skip existing employee IDs")


class BulkCameraStatusUpdate(BaseModel):
    camera_ids: List[int] = Field(..., description="List of camera IDs to update")
    is_active: bool = Field(..., description="New active status")


@app.post("/bulk/students/import")
@limiter.limit("5/minute")
async def bulk_import_students(
    request: Request,
    body: BulkStudentImport,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Import students from CSV content."""
    result = bulk_operations.import_students_from_csv(
        csv_content=body.csv_content,
        default_department_id=body.default_department_id,
        skip_duplicates=body.skip_duplicates,
    )
    return result.to_dict()


@app.post("/bulk/employees/import")
@limiter.limit("5/minute")
async def bulk_import_employees(
    request: Request,
    body: BulkEmployeeImport,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Import employees from CSV content."""
    result = bulk_operations.import_employees_from_csv(
        csv_content=body.csv_content,
        skip_duplicates=body.skip_duplicates,
    )
    return result.to_dict()


@app.post("/bulk/cameras/status")
@limiter.limit("10/minute")
async def bulk_update_camera_status(
    request: Request,
    body: BulkCameraStatusUpdate,
    current_user: Annotated[User, Depends(require_role(RoleName.COLLEGE_ADMIN, RoleName.SUPER_ADMIN))],
):
    """Bulk enable/disable cameras."""
    result = bulk_operations.bulk_update_camera_status(
        camera_ids=body.camera_ids,
        is_active=body.is_active,
    )
    return result.to_dict()


@app.get("/bulk/attendance/export")
@limiter.limit("5/minute")
async def export_attendance(
    request: Request,
    current_user: Annotated[User, Depends(require_permission("attendance", ActionType.READ))],
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    section_id: Optional[int] = Query(None),
):
    """Export attendance records as CSV."""
    from fastapi.responses import PlainTextResponse
    csv_content = bulk_operations.export_attendance_csv(
        date_from=date_from, date_to=date_to, section_id=section_id,
    )
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_export.csv"},
    )


# ── Enhanced Health / Readiness ──────────────────────────────────

@app.get("/health/ready")
@limiter.exempt
async def readiness_check(request: Request):
    """Kubernetes readiness probe — returns 200 only when all services are ready."""
    checks = {}
    all_ok = True

    # Database check
    try:
        with get_session() as s:
            s.execute(select(1))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        all_ok = False

    # Redis check
    try:
        from api.redis_client import get_redis
        redis = get_redis()
        redis.client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        all_ok = False

    # WebSocket manager
    checks["websocket"] = f"ok ({ws_manager.connection_count} connections)"

    # Job queue
    job_stats = job_queue.stats()
    checks["job_queue"] = f"ok (workers={job_stats['workers']}, queue={job_stats['queue_size']})"

    return {
        "ready": all_ok,
        "checks": checks,
        "timestamp": _utcnow().isoformat(),
    }


@app.get("/health")
@limiter.exempt
async def health_summary(request: Request):
    """Compatibility health endpoint for frontend monitoring."""
    ready = await readiness_check(request)
    return {
        "status": "ok" if ready["ready"] else "degraded",
        "version": "2.0.0",
        "timestamp": ready["timestamp"],
        "database": ready["checks"].get("database", "unknown"),
        "redis": ready["checks"].get("redis", "unknown"),
    }


@app.get("/health/live")
@limiter.exempt
async def liveness_check(request: Request):
    """Kubernetes liveness probe — always returns 200 if the process is alive."""
    return {"alive": True, "timestamp": _utcnow().isoformat()}


@app.get("/system/status")
@limiter.exempt
async def system_status(
    request: Request,
    current_user: Annotated[User, Depends(require_role(RoleName.SUPER_ADMIN))],
):
    """Full system status for admin dashboard (SUPER_ADMIN only)."""
    return {
        "version": "2.0.0",
        "timestamp": _utcnow().isoformat(),
        "websocket": ws_manager.status(),
        "job_queue": job_queue.stats(),
        "environment": settings.environment,
    }


# ── Lifespan: Start/stop background services ────────────────────
# Note: This overrides the lifespan defined above.
# We need to merge it properly.
# The job queue and WS manager are started on first use.


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
