"""
Seed Script — First Admin User & RBAC Bootstrap
=================================================

Creates the initial SUPER_ADMIN user and seeds all roles, permissions,
and role–permission assignments needed by the Face Recognition AI API.

Idempotent — safe to run multiple times.  Skips any record that already
exists (identified by unique name).

Usage
-----
    python scripts/seed_admin.py

Configuration
-------------
Environment variables (all optional, defaults shown):

    ADMIN_USERNAME      admin          Login username
    ADMIN_EMAIL         admin@college.edu  Email address
    ADMIN_PASSWORD      AutoR!0t!ze*9!  Password (must meet strength policy)
    DB_TYPE             sqlite         Database type (sqlite | postgres)
    DATABASE_URL        —              Required if DB_TYPE=postgres

Seeds
-----
    • 7 roles (SUPER_ADMIN → STAFF)
    • 60+ permissions covering all API resources (11 resources × 5 actions + extras)
    • SUPER_ADMIN role gets *every* permission
    • COLLEGE_ADMIN role gets a reasonable management subset
    • Admin user with SUPER_ADMIN and COLLEGE_ADMIN roles assigned
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import project modules
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import bcrypt

from database.database import get_session, init_db
from database.models import (
    ActionType,
    Permission,
    Role,
    RoleName,
    User,
    user_roles,
    role_permissions,
    _utcnow,
)

# ── Config ──────────────────────────────────────────────────────────

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@college.edu")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "AutoR!0t!ze*9!")


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt, returning a salt+hash string."""
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

# ── All resources used by the API ──────────────────────────────────

RESOURCES = [
    "students",
    "employees",
    "cameras",
    "attendance",
    "analytics",
    "enrollment",
    "mfa",
    "users",
    "unknown_faces",
    "jobs",
    "audit_logs",
]

# All 5 actions per resource
ACTIONS = [
    ActionType.CREATE,
    ActionType.READ,
    ActionType.UPDATE,
    ActionType.DELETE,
    ActionType.EXECUTE,
]


# ── Helpers ─────────────────────────────────────────────────────────

def _get_or_create_role(session, name: str, description: str) -> Role:
    """Fetch an existing role by name or create a new one."""
    role = session.query(Role).filter(Role.name == name).first()
    if role:
        print(f"  [SKIP] Role '{name}' already exists")
        return role
    role = Role(name=name, description=description)
    session.add(role)
    session.flush()
    print(f"  [ OK ] Created role '{name}'")
    return role


def _get_or_create_permission(
    session, resource: str, action: ActionType
) -> Permission:
    """Fetch an existing permission by (resource, action) or create one."""
    perm = (
        session.query(Permission)
        .filter(Permission.resource == resource, Permission.action == action.value)
        .first()
    )
    if perm:
        return perm
    perm = Permission(
        resource=resource,
        action=action.value,
        description=f"Allows {action.value.lower()} on {resource}",
    )
    session.add(perm)
    session.flush()
    return perm


def _get_or_create_user(
    session, username: str, email: str, password: str
) -> User:
    """Fetch an existing user by username or create a new one."""
    user = session.query(User).filter(User.username == username).first()
    if user:
        print(f"  [SKIP] User '{username}' already exists")
        return user

    password_hash = _hash_password(password)
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        auth_method="local",
        is_active=True,
    )
    session.add(user)
    session.flush()
    print(f"  [ OK ] Created user '{username}' ({email})")
    return user


def _assign_role(session, user: User, role: Role) -> None:
    """Assign a role to a user (idempotent via unique constraint)."""
    existing = session.execute(
        user_roles.select().where(
            user_roles.c.user_id == user.id,
            user_roles.c.role_id == role.id,
        )
    ).first()
    if existing:
        print(f"  [SKIP] User '{user.username}' already has role '{role.name}' ")
        return
    session.execute(
        user_roles.insert().values(user_id=user.id, role_id=role.id)
    )
    print(f"  [ OK ] Assigned role '{role.name}' to user '{user.username}'")


def _assign_permission(session, role: Role, permission: Permission) -> None:
    """Assign a permission to a role (idempotent via unique constraint)."""
    existing = session.execute(
        role_permissions.select().where(
            role_permissions.c.role_id == role.id,
            role_permissions.c.permission_id == permission.id,
        )
    ).first()
    if existing:
        return
    session.execute(
        role_permissions.insert().values(
            role_id=role.id, permission_id=permission.id
        )
    )


# ── Main ────────────────────────────────────────────────────────────

def main() -> None:
    """Bootstrap the database with roles, permissions, and the admin user."""
    print("=" * 60)
    print("  Face Recognition AI — Database Seed")
    print("=" * 60)

    # Step 0 — Ensure database tables exist
    print("\n[ INIT ] Initialising database...")
    init_db()
    print("  [ OK ] Database tables ready")

    # Step 1 — Seed all 7 roles
    print("\n[ ROLES ] Seeding roles...")
    with get_session() as session:
        role_defs = {
            RoleName.SUPER_ADMIN: "Full system access — can perform any operation",
            RoleName.COLLEGE_ADMIN: "College-level administrator with broad management access",
            RoleName.HOD: "Head of Department — department-level course & staff management",
            RoleName.FACULTY: "Teaching faculty — can mark attendance and view course data",
            RoleName.SECURITY: "Security personnel — can view cameras and unknown faces",
            RoleName.STUDENT: "Student — can view own attendance records",
            RoleName.STAFF: "Non-academic staff — basic attendance access",
        }

        roles = {}
        for role_name, description in role_defs.items():
            roles[role_name] = _get_or_create_role(session, role_name.value, description)

        # Step 2 — Seed all permissions
        print("\n[ PERMS ] Seeding permissions...")
        permissions = {}
        for resource in RESOURCES:
            for action in ACTIONS:
                perm = _get_or_create_permission(session, resource, action)
                permissions[(resource, action.value)] = perm

        # Also create specific permissions used in the codebase
        extra_permissions = [
            ("institutions", ActionType.READ),
            ("departments", ActionType.READ),
            ("courses", ActionType.READ),
            ("sections", ActionType.READ),
            ("classrooms", ActionType.READ),
        ]
        for resource, action in extra_permissions:
            perm = _get_or_create_permission(session, resource, action)
            permissions[(resource, action.value)] = perm

        print(f"  [ OK ] {len(permissions)} permissions ready")

        # Step 3 — Assign ALL permissions to SUPER_ADMIN
        print("\n[ SUPER_ADMIN ] Assigning all permissions...")
        count = 0
        for perm in permissions.values():
            _assign_permission(session, roles[RoleName.SUPER_ADMIN], perm)
            count += 1
        session.flush()
        print(f"  [ OK ] {count} permissions assigned to SUPER_ADMIN")

        # Step 4 — Assign reasonable permissions to COLLEGE_ADMIN
        print("\n[ COLLEGE_ADMIN ] Assigning permissions...")
        college_admin_actions = [
            ActionType.CREATE,
            ActionType.READ,
            ActionType.UPDATE,
            ActionType.DELETE,
            ActionType.EXECUTE,
        ]
        college_admin_resources = [
            "students", "employees", "cameras", "attendance",
            "enrollment", "analytics", "users",
        ]
        ca_count = 0
        for resource in college_admin_resources:
            for action in college_admin_actions:
                key = (resource, action.value)
                if key in permissions:
                    _assign_permission(session, roles[RoleName.COLLEGE_ADMIN], permissions[key])
                    ca_count += 1
        session.flush()
        print(f"  [ OK ] {ca_count} permissions assigned to COLLEGE_ADMIN")

        # Step 5 — Create the admin user
        print(f"\n[ USER ] Creating admin user '{ADMIN_USERNAME}'...")
        admin_user = _get_or_create_user(
            session, ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD
        )

        # Step 6 — Assign SUPER_ADMIN role
        print("\n[ ASSIGN ] Assigning SUPER_ADMIN role...")
        _assign_role(session, admin_user, roles[RoleName.SUPER_ADMIN])

        # Also assign COLLEGE_ADMIN for full access via either role
        _assign_role(session, admin_user, roles[RoleName.COLLEGE_ADMIN])

        # Commit everything
        session.commit()

    # ── Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [ DONE ] Seed complete!")
    print("=" * 60)
    print(f"\n  Admin credentials:")
    print(f"    Username: {ADMIN_USERNAME}")
    print(f"    Email:    {ADMIN_EMAIL}")
    print(f"    Password: {'<hidden>' if ADMIN_PASSWORD else '<not set>'}")
    print(f"    (set ADMIN_PASSWORD env var to override)")
    print()
    print(f"  Roles seeded:     {len(role_defs)}")
    print(f"  Permissions seeded: {len(permissions)}")
    print()


if __name__ == "__main__":
    main()
