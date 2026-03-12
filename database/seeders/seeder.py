"""
Database Seeder
===============
Seeds the database with initial data required for the application to function.

Usage:
    python migrate.py seed
"""

import bcrypt
from datetime import datetime


def run(conn):
    """Seed the database with initial data."""
    print("  Seeding database...\n")

    _seed_super_admin(conn)
    _seed_default_config(conn)

    print("\n  Seeding complete.")


def _seed_super_admin(conn):
    """Create the default super admin user (id=1)."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE id = 1")
        if cur.fetchone():
            print("  [SKIP] Super admin already exists (id=1)")
            return

        password_hash = bcrypt.hashpw('4321'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        cur.execute("""
            INSERT INTO users (id, username, email, password_hash, display_name, role, status, created_at, updated_at)
            VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('admin', 'admin@voicelink.local', password_hash, 'System Admin', 'super_admin', 'offline', now, now))

    conn.commit()
    print("  [OK] Super admin created (username: admin, password: 4321)")


def _seed_default_config(conn):
    """Seed default system configuration entries."""
    defaults = [
        ('app_name', 'VoiceLink', 'Application display name'),
        ('app_version', '1.0.0', 'Current application version'),
        ('max_file_size_mb', '50', 'Maximum file upload size in MB'),
        ('allow_registration', 'true', 'Whether new user registration is enabled'),
    ]

    with conn.cursor() as cur:
        for key, value, description in defaults:
            cur.execute("SELECT id FROM system_config WHERE `key` = %s", (key,))
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO system_config (`key`, value, description) VALUES (%s, %s, %s)",
                (key, value, description)
            )
            print(f"  [OK] Config: {key} = {value}")

    conn.commit()
