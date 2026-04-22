"""
AlertBot Authentication & Role-Based Access Control
Handles user login verification and project-level access enforcement.
"""

import hashlib
import sqlite3
from dataclasses import dataclass, field
from typing import Optional
from database import get_connection


@dataclass
class AuthUser:
    """Represents an authenticated session user."""
    id: int
    username: str
    full_name: str
    email: str
    role: str                        # 'admin' | 'pm'
    project_ids: list[int] = field(default_factory=list)   # empty for admins (means all)
    project_names: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_pm(self) -> bool:
        return self.role == "pm"

    def can_access_project(self, project_id: int) -> bool:
        """Admins can access any project; PMs only their assigned ones."""
        if self.is_admin:
            return True
        return project_id in self.project_ids

    def accessible_project_ids(self) -> Optional[list[int]]:
        """Returns None for admins (all projects); list for PMs."""
        if self.is_admin:
            return None
        return self.project_ids


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(username: str, password: str) -> Optional[AuthUser]:
    """
    Verifies credentials against the database.
    Returns an AuthUser on success, None on failure.
    """
    conn = get_connection()
    try:
        hashed = _hash_password(password)
        row = conn.execute(
            """
            SELECT id, username, full_name, email, role
            FROM users
            WHERE username = ? AND password = ? AND is_active = 1
            """,
            (username, hashed),
        ).fetchone()

        if not row:
            return None

        user = AuthUser(
            id=row["id"],
            username=row["username"],
            full_name=row["full_name"],
            email=row["email"],
            role=row["role"],
        )

        # Load assigned projects for PM users
        if user.is_pm:
            assignments = conn.execute(
                """
                SELECT p.id, p.name
                FROM project_assignments pa
                JOIN projects p ON pa.project_id = p.id
                WHERE pa.user_id = ?
                """,
                (user.id,),
            ).fetchall()
            user.project_ids = [r["id"] for r in assignments]
            user.project_names = [r["name"] for r in assignments]

        return user

    finally:
        conn.close()


def get_all_users_summary() -> list[dict]:
    """Returns a list of users (for admin display). No passwords."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, username, full_name, email, role, is_active FROM users ORDER BY role, username"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
