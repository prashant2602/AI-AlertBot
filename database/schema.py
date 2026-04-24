"""
AlertBot Database Schema
Defines all table creation SQL for the AlertBot SQLite database.
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,   -- SHA-256 hashed
    full_name   TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    role        TEXT    NOT NULL CHECK(role IN ('admin', 'pm')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    is_active   INTEGER NOT NULL DEFAULT 1
);
"""

CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    description TEXT,
    status      TEXT    NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'on_hold', 'completed', 'cancelled')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_PROJECT_ASSIGNMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS project_assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    assigned_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, project_id)
);
"""

CREATE_ALERTS_TABLE = """
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL REFERENCES projects(id),
    title        TEXT    NOT NULL,
    description  TEXT,
    severity     TEXT    NOT NULL CHECK(severity IN ('critical', 'high', 'medium', 'low', 'info')),
    category     TEXT    NOT NULL DEFAULT 'general' CHECK(category IN ('performance', 'security', 'budget', 'schedule', 'quality', 'dependency', 'general')),
    status       TEXT    NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'acknowledged', 'resolved', 'closed')),
    raised_by    TEXT    NOT NULL DEFAULT 'system',
    assigned_to  TEXT,
    alert_date   TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_at  TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_ALERT_COMMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS alert_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id   INTEGER NOT NULL REFERENCES alerts(id),
    username   TEXT    NOT NULL,
    full_name  TEXT    NOT NULL,
    comment    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_PROJECTS_TABLE,
    CREATE_PROJECT_ASSIGNMENTS_TABLE,
    CREATE_ALERTS_TABLE,
    CREATE_ALERT_COMMENTS_TABLE,
]
