"""
AlertBot Alert Query Engine
Fetches alerts from SQLite with role-based access control baked in.
All public functions accept an AuthUser and enforce access rules silently.
"""

from typing import Optional
from database import get_connection
from auth import AuthUser


def _project_filter_clause(user: AuthUser) -> tuple[str, list]:
    """
    Generates SQL fragment and params for project access control.
    Admins → no restriction.
    PMs    → only their assigned project IDs.
    """
    if user.is_admin:
        return "", []
    ids = user.project_ids
    if not ids:
        # PM with no projects assigned — deny all
        return "AND 1=0", []
    placeholders = ",".join("?" * len(ids))
    return f"AND a.project_id IN ({placeholders})", ids


def get_alerts(
    user: AuthUser,
    project_name: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,    # ISO date string YYYY-MM-DD
    date_to: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Retrieve alerts with optional filters. RBAC enforced.
    Returns list of dicts with all alert + project fields.
    """
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)

        conditions = [f"1=1 {rbac_clause}"]
        params: list = rbac_params[:]

        if project_name:
            conditions.append("LOWER(p.name) LIKE LOWER(?)")
            params.append(f"%{project_name}%")

        if severity:
            sev_list = [s.strip().lower() for s in severity.split(",")]
            placeholders = ",".join("?" * len(sev_list))
            conditions.append(f"LOWER(a.severity) IN ({placeholders})")
            params.extend(sev_list)

        if status:
            conditions.append("LOWER(a.status) = LOWER(?)")
            params.append(status)

        if category:
            conditions.append("LOWER(a.category) = LOWER(?)")
            params.append(category)

        if date_from:
            conditions.append("DATE(a.alert_date) >= DATE(?)")
            params.append(date_from)

        if date_to:
            conditions.append("DATE(a.alert_date) <= DATE(?)")
            params.append(date_to)

        where = " AND ".join(conditions)

        sql = f"""
            SELECT
                a.id, a.title, a.description, a.severity, a.category,
                a.status, a.raised_by, a.alert_date, a.resolved_at,
                p.id AS project_id, p.name AS project_name, p.status AS project_status
            FROM alerts a
            JOIN projects p ON a.project_id = p.id
            WHERE {where}
            ORDER BY
                CASE a.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high'     THEN 2
                    WHEN 'medium'   THEN 3
                    WHEN 'low'      THEN 4
                    ELSE 5
                END,
                a.alert_date DESC
            LIMIT ?
        """
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    finally:
        conn.close()


def get_alert_by_id(user: AuthUser, alert_id: int) -> Optional[dict]:
    """Fetch a single alert by ID, with RBAC check."""
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)
        sql = f"""
            SELECT a.*, p.name AS project_name, p.status AS project_status
            FROM alerts a
            JOIN projects p ON a.project_id = p.id
            WHERE a.id = ? {rbac_clause}
        """
        row = conn.execute(sql, [alert_id] + rbac_params).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_alert_summary(user: AuthUser) -> dict:
    """
    Returns aggregated statistics for accessible alerts.
    Useful for dashboard / overview queries.
    """
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)

        # Total by severity
        by_severity = conn.execute(f"""
            SELECT a.severity, COUNT(*) as count
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.status NOT IN ('resolved','closed') {rbac_clause}
            GROUP BY a.severity
        """, rbac_params).fetchall()

        # Total by status
        by_status = conn.execute(f"""
            SELECT a.status, COUNT(*) as count
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE 1=1 {rbac_clause}
            GROUP BY a.status
        """, rbac_params).fetchall()

        # Total by project
        by_project = conn.execute(f"""
            SELECT p.name, COUNT(*) as total,
                   SUM(CASE WHEN a.severity='critical' THEN 1 ELSE 0 END) as critical,
                   SUM(CASE WHEN a.severity='high' THEN 1 ELSE 0 END) as high,
                   SUM(CASE WHEN a.status NOT IN ('resolved','closed') THEN 1 ELSE 0 END) as open_count
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE 1=1 {rbac_clause}
            GROUP BY p.id, p.name
            ORDER BY critical DESC, high DESC
        """, rbac_params).fetchall()

        # Total by category
        by_category = conn.execute(f"""
            SELECT a.category, COUNT(*) as count
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.status NOT IN ('resolved','closed') {rbac_clause}
            GROUP BY a.category
            ORDER BY count DESC
        """, rbac_params).fetchall()

        return {
            "by_severity": [dict(r) for r in by_severity],
            "by_status": [dict(r) for r in by_status],
            "by_project": [dict(r) for r in by_project],
            "by_category": [dict(r) for r in by_category],
        }

    finally:
        conn.close()


def create_alert(
    user: AuthUser,
    project_name: str,
    title: str,
    description: str = "",
    severity: str = "medium",
    category: str = "general",
    assigned_to: str = None,
) -> dict:
    """Create a new alert. PMs can only create for their assigned projects."""
    conn = get_connection()
    try:
        project = conn.execute(
            "SELECT id, name FROM projects WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{project_name}%",)
        ).fetchone()

        if not project:
            return {"error": f"Project '{project_name}' not found."}

        if not user.is_admin and project["id"] not in user.project_ids:
            return {"error": f"You don't have access to project '{project['name']}'."}

        # Validate assigned_to user exists if provided
        assignee = None
        if assigned_to:
            assignee = conn.execute(
                "SELECT username, full_name, role FROM users WHERE username = ? AND is_active = 1",
                (assigned_to,)
            ).fetchone()
            if not assignee:
                return {"error": f"User '{assigned_to}' not found."}

        cursor = conn.execute("""
            INSERT INTO alerts
                (project_id, title, description, severity, category, status, raised_by, assigned_to, alert_date)
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?, datetime('now'))
        """, (project["id"], title, description, severity, category, user.username, assigned_to))
        conn.commit()

        alert_id = cursor.lastrowid

        # Get PMs for this project
        pms = conn.execute("""
            SELECT u.username, u.full_name
            FROM project_assignments pa JOIN users u ON u.id = pa.user_id
            WHERE pa.project_id = ? AND u.role = 'pm'
        """, (project["id"],)).fetchall()

        return {
            "created": True,
            "alert_id": alert_id,
            "title": title,
            "project": project["name"],
            "severity": severity,
            "category": category,
            "status": "open",
            "raised_by": user.full_name,
            "assigned_to": dict(assignee) if assignee else None,
            "project_managers": [dict(p) for p in pms],
        }
    finally:
        conn.close()


def assign_alert(user: AuthUser, alert_id: int, assigned_to: str) -> dict:
    """Assign an alert to a user. RBAC enforced."""
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)
        alert = conn.execute(f"""
            SELECT a.id, a.title, p.name AS project_name, p.id AS project_id
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.id = ? {rbac_clause}
        """, [alert_id] + rbac_params).fetchone()

        if not alert:
            return {"error": f"Alert #{alert_id} not found or not accessible."}

        assignee = conn.execute(
            "SELECT username, full_name, role FROM users WHERE username = ? AND is_active = 1",
            (assigned_to,)
        ).fetchone()

        if not assignee:
            return {"error": f"User '{assigned_to}' not found."}

        conn.execute("UPDATE alerts SET assigned_to = ? WHERE id = ?", (assigned_to, alert_id))
        conn.commit()

        # Get PMs for this project
        pms = conn.execute("""
            SELECT u.username, u.full_name
            FROM project_assignments pa JOIN users u ON u.id = pa.user_id
            WHERE pa.project_id = ? AND u.role = 'pm'
        """, (alert["project_id"],)).fetchall()

        return {
            "assigned": True,
            "alert_id": alert_id,
            "alert_title": alert["title"],
            "project": alert["project_name"],
            "assigned_to_username": assignee["username"],
            "assigned_to_name": assignee["full_name"],
            "assigned_to_role": assignee["role"],
            "project_managers": [dict(p) for p in pms],
        }
    finally:
        conn.close()


def add_alert_comment(user: AuthUser, alert_id: int, comment_text: str) -> dict:
    """Add a comment to an alert. RBAC enforced."""
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)
        alert = conn.execute(f"""
            SELECT a.id, a.title, p.name AS project_name
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.id = ? {rbac_clause}
        """, [alert_id] + rbac_params).fetchone()

        if not alert:
            return {"error": f"Alert #{alert_id} not found or not accessible."}

        conn.execute("""
            INSERT INTO alert_comments (alert_id, username, full_name, comment)
            VALUES (?, ?, ?, ?)
        """, (alert_id, user.username, user.full_name, comment_text))
        conn.commit()

        return {
            "commented": True,
            "alert_id": alert_id,
            "alert_title": alert["title"],
            "project": alert["project_name"],
            "comment": comment_text,
            "by_username": user.username,
            "by_name": user.full_name,
        }
    finally:
        conn.close()


def get_alert_comments(user: AuthUser, alert_id: int) -> dict:
    """Get all comments for an alert. RBAC enforced."""
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)
        alert = conn.execute(f"""
            SELECT a.id, a.title, a.status, a.severity, a.assigned_to,
                   p.name AS project_name
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.id = ? {rbac_clause}
        """, [alert_id] + rbac_params).fetchone()

        if not alert:
            return {"error": f"Alert #{alert_id} not found or not accessible."}

        comments = conn.execute("""
            SELECT id, username, full_name, comment, created_at
            FROM alert_comments
            WHERE alert_id = ?
            ORDER BY created_at ASC
        """, (alert_id,)).fetchall()

        return {
            "alert_id": alert_id,
            "alert_title": alert["title"],
            "project": alert["project_name"],
            "severity": alert["severity"],
            "status": alert["status"],
            "assigned_to": alert["assigned_to"],
            "comments": [dict(c) for c in comments],
            "total_comments": len(comments),
        }
    finally:
        conn.close()


def delete_alert(user: AuthUser, alert_id: int) -> dict:
    """Delete an alert. Admins can delete any; PMs only from their projects."""
    conn = get_connection()
    try:
        rbac_clause, rbac_params = _project_filter_clause(user)
        alert = conn.execute(f"""
            SELECT a.id, a.title, p.name AS project_name
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.id = ? {rbac_clause}
        """, [alert_id] + rbac_params).fetchone()

        if not alert:
            return {"error": f"Alert #{alert_id} not found or not accessible."}

        # Delete comments first (foreign key)
        conn.execute("DELETE FROM alert_comments WHERE alert_id = ?", (alert_id,))
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()

        return {
            "deleted": True,
            "alert_id": alert_id,
            "alert_title": alert["title"],
            "project": alert["project_name"],
            "deleted_by": user.full_name,
        }
    finally:
        conn.close()


def update_alert_severity(user: AuthUser, alert_id: int, new_severity: str) -> dict:
    """Admin-only: update the severity of an alert."""
    if not user.is_admin:
        return {"error": "Only admins can change alert severity."}

    valid = ("critical", "high", "medium", "low", "info")
    if new_severity.lower() not in valid:
        return {"error": f"Invalid severity '{new_severity}'. Must be one of: {', '.join(valid)}."}

    conn = get_connection()
    try:
        alert = conn.execute("""
            SELECT a.id, a.title, a.severity, p.name AS project_name
            FROM alerts a JOIN projects p ON a.project_id = p.id
            WHERE a.id = ?
        """, (alert_id,)).fetchone()

        if not alert:
            return {"error": f"Alert #{alert_id} not found."}

        old_severity = alert["severity"]
        conn.execute("UPDATE alerts SET severity = ? WHERE id = ?", (new_severity.lower(), alert_id))
        conn.commit()

        return {
            "updated": True,
            "alert_id": alert_id,
            "alert_title": alert["title"],
            "project": alert["project_name"],
            "old_severity": old_severity,
            "new_severity": new_severity.lower(),
            "changed_by": user.full_name,
        }
    finally:
        conn.close()


def get_alerts_by_manager(user: AuthUser) -> list[dict]:
    """
    Admin-only: returns alert counts per project manager, ranked by total alerts.
    Each entry: {username, full_name, projects, total_alerts, open, critical, high}
    """
    if not user.is_admin:
        return []
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                u.username,
                u.full_name,
                COUNT(DISTINCT p.id)                                             AS project_count,
                GROUP_CONCAT(DISTINCT p.name)                                    AS projects,
                COUNT(a.id)                                                      AS total_alerts,
                SUM(CASE WHEN a.status NOT IN ('resolved','closed') THEN 1 ELSE 0 END) AS open_alerts,
                SUM(CASE WHEN a.severity = 'critical' THEN 1 ELSE 0 END)        AS critical_alerts,
                SUM(CASE WHEN a.severity = 'high'     THEN 1 ELSE 0 END)        AS high_alerts
            FROM users u
            JOIN project_assignments pa ON pa.user_id = u.id
            JOIN projects p             ON p.id = pa.project_id
            LEFT JOIN alerts a          ON a.project_id = p.id
            WHERE u.role = 'pm'
            GROUP BY u.id, u.username, u.full_name
            ORDER BY total_alerts DESC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_project_assignments(user: AuthUser) -> list[dict]:
    """
    Admin-only: returns every project with its assigned PMs.
    Each entry: {project, status, managers: [{username, full_name}]}
    """
    if not user.is_admin:
        return []
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT
                p.name  AS project,
                p.status AS project_status,
                u.username,
                u.full_name
            FROM projects p
            LEFT JOIN project_assignments pa ON pa.project_id = p.id
            LEFT JOIN users u ON u.id = pa.user_id AND u.role = 'pm'
            ORDER BY p.name, u.full_name
        """).fetchall()

        # Group by project
        from collections import defaultdict
        grouped: dict = defaultdict(lambda: {"project": "", "project_status": "", "managers": []})
        for r in rows:
            key = r["project"]
            grouped[key]["project"] = r["project"]
            grouped[key]["project_status"] = r["project_status"]
            if r["username"]:
                grouped[key]["managers"].append({
                    "username": r["username"],
                    "full_name": r["full_name"],
                })

        return list(grouped.values())
    finally:
        conn.close()


def get_projects_for_user(user: AuthUser) -> list[dict]:
    """Returns the list of projects accessible to this user."""
    conn = get_connection()
    try:
        if user.is_admin:
            rows = conn.execute(
                "SELECT id, name, description, status FROM projects ORDER BY name"
            ).fetchall()
        else:
            placeholders = ",".join("?" * len(user.project_ids))
            rows = conn.execute(
                f"SELECT id, name, description, status FROM projects WHERE id IN ({placeholders}) ORDER BY name",
                user.project_ids,
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
