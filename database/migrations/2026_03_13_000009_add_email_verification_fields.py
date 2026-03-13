"""
Migration: Add Email Verification and Password Reset Fields to Users Table
Created: 2026-03-13
Description: Adds email_verified, verification_token, verification_token_expires,
             reset_token, and reset_token_expires columns to the users table.
"""


def up(conn):
    """Apply the migration."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE users
                ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0 AFTER public_key,
                ADD COLUMN verification_token VARCHAR(255) DEFAULT NULL AFTER email_verified,
                ADD COLUMN verification_token_expires DATETIME DEFAULT NULL AFTER verification_token,
                ADD COLUMN reset_token VARCHAR(255) DEFAULT NULL AFTER verification_token_expires,
                ADD COLUMN reset_token_expires DATETIME DEFAULT NULL AFTER reset_token
        """)
        # Mark the super admin (id=1) as verified
        cur.execute("UPDATE users SET email_verified = 1 WHERE id = 1")
    conn.commit()


def down(conn):
    """Reverse the migration."""
    with conn.cursor() as cur:
        cur.execute("""
            ALTER TABLE users
                DROP COLUMN email_verified,
                DROP COLUMN verification_token,
                DROP COLUMN verification_token_expires,
                DROP COLUMN reset_token,
                DROP COLUMN reset_token_expires
        """)
    conn.commit()
