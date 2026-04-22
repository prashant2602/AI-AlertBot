"""
AlertBot Database Seeder
Creates and seeds the SQLite database with realistic sample data.
Run this script once to initialize the database.
"""

import sqlite3
import hashlib
import os
from pathlib import Path
from database.schema import ALL_TABLES

DB_PATH = Path(__file__).parent.parent / "alertbot.db"


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables (idempotent — uses CREATE IF NOT EXISTS)."""
    conn = get_connection()
    try:
        with conn:
            for ddl in ALL_TABLES:
                conn.execute(ddl)
        print(f"[OK] Tables ready in {DB_PATH}")
    except Exception as e:
        print(f"[ERROR] Could not create tables: {e}")
        raise
    finally:
        conn.close()


def seed_db():
    """Seed the database with sample users, projects, and alerts."""
    conn = get_connection()

    with conn:
        # ── Users ──────────────────────────────────────────────────────────
        users = [
            # Admins
            ("alice_admin",  hash_password("admin123"), "Alice Johnson",    "alice@company.com",   "admin"),
            ("bob_admin",    hash_password("admin456"), "Bob Smith",        "bob@company.com",     "admin"),
            # Project Managers
            ("carol_pm",     hash_password("carol123"), "Carol Williams",   "carol@company.com",   "pm"),
            ("david_pm",     hash_password("david123"), "David Brown",      "david@company.com",   "pm"),
            ("eve_pm",       hash_password("eve123"),   "Eve Davis",        "eve@company.com",     "pm"),
            ("frank_pm",     hash_password("frank123"), "Frank Miller",     "frank@company.com",   "pm"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO users (username, password, full_name, email, role) VALUES (?,?,?,?,?)",
            users
        )

        # ── Projects ──────────────────────────────────────────────────────
        projects = [
            ("Alpha Portal",       "Customer-facing web portal redesign",                "active"),
            ("Beta Analytics",     "Internal business intelligence platform",            "active"),
            ("Gamma Migration",    "Legacy system migration to cloud infrastructure",    "active"),
            ("Delta Security",     "Enterprise-wide security hardening initiative",      "active"),
            ("Epsilon ML",         "Machine learning pipeline for demand forecasting",   "on_hold"),
            ("Zeta Mobile",        "Cross-platform mobile application",                  "active"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO projects (name, description, status) VALUES (?,?,?)",
            projects
        )

        # ── Project Assignments (PM → Projects) ────────────────────────────
        # carol_pm  → Alpha Portal, Beta Analytics
        # david_pm  → Gamma Migration, Delta Security
        # eve_pm    → Epsilon ML, Zeta Mobile
        # frank_pm  → Zeta Mobile (shared PM)
        assignments_raw = [
            ("carol_pm",  "Alpha Portal"),
            ("carol_pm",  "Beta Analytics"),
            ("david_pm",  "Gamma Migration"),
            ("david_pm",  "Delta Security"),
            ("eve_pm",    "Epsilon ML"),
            ("eve_pm",    "Zeta Mobile"),
            ("frank_pm",  "Zeta Mobile"),
        ]
        for username, project_name in assignments_raw:
            conn.execute("""
                INSERT OR IGNORE INTO project_assignments (user_id, project_id)
                SELECT u.id, p.id
                FROM users u, projects p
                WHERE u.username = ? AND p.name = ?
            """, (username, project_name))

        # ── Alerts ─────────────────────────────────────────────────────────
        alerts = [
            # Alpha Portal
            ("Alpha Portal", "Login Page Load Time > 5s",            "Page load time exceeds SLA threshold of 3 seconds during peak hours.",          "high",     "performance", "open",         "system",    "2026-04-20 09:15:00"),
            ("Alpha Portal", "SSL Certificate Expiring in 10 Days",  "SSL cert expires on 2026-04-30. Renewal not yet initiated.",                     "critical", "security",    "open",         "system",    "2026-04-21 08:00:00"),
            ("Alpha Portal", "UI Regression in Safari 17",           "Dropdown menus broken on Safari 17. Affects ~20% of users.",                     "medium",   "quality",     "acknowledged", "carol_pm",  "2026-04-18 14:30:00"),
            ("Alpha Portal", "Third-party API Rate Limit Hit",       "Payment gateway API rate limit reached twice this week.",                        "high",     "dependency",  "open",         "system",    "2026-04-19 11:45:00"),
            ("Alpha Portal", "Budget Overage: Cloud Hosting",        "Cloud hosting spend 15% over budget for Q2.",                                    "medium",   "budget",      "open",         "finance",   "2026-04-15 10:00:00"),

            # Beta Analytics
            ("Beta Analytics", "Dashboard Query Timeout",            "5 reports timing out on the analytics dashboard. Affecting finance team.",       "high",     "performance", "open",         "system",    "2026-04-21 07:30:00"),
            ("Beta Analytics", "Data Pipeline Failure - ETL Job",    "Nightly ETL job failed for the 3rd consecutive day. Data is stale.",             "critical", "general",     "open",         "system",    "2026-04-21 02:00:00"),
            ("Beta Analytics", "Unauthorized Access Attempt Logged", "3 failed login attempts from unknown IP 203.0.113.45.",                          "high",     "security",    "acknowledged", "carol_pm",  "2026-04-20 23:15:00"),
            ("Beta Analytics", "Report Export Feature Broken",       "CSV export returns empty files for date ranges > 30 days.",                      "medium",   "quality",     "open",         "system",    "2026-04-17 16:00:00"),
            ("Beta Analytics", "Schedule Delay: Q2 Dashboard",       "Q2 executive dashboard delivery delayed by 1 week.",                             "low",      "schedule",    "open",         "carol_pm",  "2026-04-10 09:00:00"),

            # Gamma Migration
            ("Gamma Migration", "Database Replication Lag > 2 min",  "Replication lag between primary and replica exceeds acceptable threshold.",      "critical", "performance", "open",         "system",    "2026-04-21 06:45:00"),
            ("Gamma Migration", "Rollback Plan Not Documented",      "Phase 3 rollback procedures missing from runbook.",                              "high",     "general",     "open",         "david_pm",  "2026-04-19 13:00:00"),
            ("Gamma Migration", "Vendor SLA Breach Risk",            "Cloud vendor response time degraded; SLA breach possible by EOW.",               "medium",   "dependency",  "acknowledged", "david_pm",  "2026-04-18 10:30:00"),
            ("Gamma Migration", "Migration Window Conflict",         "Phase 4 maintenance window conflicts with fiscal year-end freeze.",              "high",     "schedule",    "open",         "david_pm",  "2026-04-16 15:00:00"),
            ("Gamma Migration", "Data Validation Errors in Phase 2", "12% of migrated records failed checksum validation.",                           "critical", "quality",     "open",         "system",    "2026-04-14 09:00:00"),

            # Delta Security
            ("Delta Security", "Unpatched CVE-2026-1234 Detected",  "Critical vulnerability found in authentication library v2.3.1.",                 "critical", "security",    "open",         "scanner",   "2026-04-21 05:00:00"),
            ("Delta Security", "Pen Test Findings: 3 High Issues",  "Latest penetration test revealed 3 high-severity vulnerabilities.",              "high",     "security",    "open",         "pentest",   "2026-04-20 17:00:00"),
            ("Delta Security", "MFA Rollout Behind Schedule",       "Multi-factor authentication rollout is 2 weeks behind plan.",                    "medium",   "schedule",    "acknowledged", "david_pm",  "2026-04-18 11:00:00"),
            ("Delta Security", "Audit Log Storage Filling Up",      "Security audit log disk usage at 87%. Projected full in 5 days.",                "high",     "general",     "open",         "system",    "2026-04-20 08:00:00"),
            ("Delta Security", "Firewall Rule Misconfiguration",    "Port 22 open to 0.0.0.0/0 on dev server. Immediate action required.",           "critical", "security",    "open",         "scanner",   "2026-04-19 20:00:00"),

            # Epsilon ML
            ("Epsilon ML", "Model Accuracy Drop to 61%",            "Demand forecasting model accuracy dropped from 78% to 61% after last retrain.",  "high",     "quality",     "open",         "system",    "2026-04-17 14:00:00"),
            ("Epsilon ML", "Training Data Pipeline Stalled",        "Data ingestion from ERP system stalled; model training blocked.",                "critical", "dependency",  "open",         "system",    "2026-04-20 09:00:00"),
            ("Epsilon ML", "GPU Cluster Budget Exceeded",           "GPU compute costs 40% over monthly budget.",                                     "medium",   "budget",      "acknowledged", "eve_pm",    "2026-04-15 16:00:00"),

            # Zeta Mobile
            ("Zeta Mobile", "App Crash Rate > 3% on Android",       "Crash rate spiked to 3.4% on Android 14 after v2.1.0 release.",                 "critical", "quality",     "open",         "system",    "2026-04-21 10:00:00"),
            ("Zeta Mobile", "Push Notification Delivery Failure",   "~18% of push notifications not delivered on iOS.",                               "high",     "general",     "open",         "system",    "2026-04-20 15:30:00"),
            ("Zeta Mobile", "App Store Review Rejected",            "iOS app rejected due to missing privacy manifest. Resubmission required.",       "high",     "schedule",    "acknowledged", "frank_pm",  "2026-04-19 09:00:00"),
            ("Zeta Mobile", "API Response Time Degraded",           "Mobile API P95 latency increased from 200ms to 850ms.",                          "medium",   "performance", "open",         "system",    "2026-04-18 12:00:00"),
            ("Zeta Mobile", "Dependency: React Native Upgrade Due", "React Native 0.73 reaches EOL in 30 days. Upgrade needed.",                     "low",      "dependency",  "open",         "system",    "2026-04-10 10:00:00"),
            ("Zeta Mobile", "QA Sign-off Delayed",                  "QA team capacity constrained; sign-off for v2.2.0 delayed by 1 week.",           "low",      "schedule",    "open",         "frank_pm",  "2026-04-16 14:00:00"),
        ]

        for (proj_name, title, desc, severity, category, status, raised_by, alert_date) in alerts:
            conn.execute("""
                INSERT OR IGNORE INTO alerts
                    (project_id, title, description, severity, category, status, raised_by, alert_date)
                SELECT p.id, ?, ?, ?, ?, ?, ?, ?
                FROM projects p WHERE p.name = ?
            """, (title, desc, severity, category, status, raised_by, alert_date, proj_name))

    conn.close()
    print("[OK] Sample data seeded successfully.")


def reset_db():
    """Drop and recreate the database."""
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"[REMOVED] Existing database at {DB_PATH}")
    init_db()
    seed_db()


if __name__ == "__main__":
    import sys
    if "--reset" in sys.argv:
        reset_db()
    else:
        init_db()
        seed_db()
