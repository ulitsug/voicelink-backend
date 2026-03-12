"""
Migration: Create Call Logs Table
Created: 2026-03-13
Description: Creates the call_logs table for tracking voice/video call history.
"""


def up(conn):
    """Apply the migration."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                caller_id INT NOT NULL,
                callee_id INT DEFAULT NULL,
                group_id INT DEFAULT NULL,
                call_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'initiated',
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                answered_at DATETIME DEFAULT NULL,
                ended_at DATETIME DEFAULT NULL,
                duration INT DEFAULT 0,
                KEY idx_call_logs_caller_id (caller_id),
                KEY idx_call_logs_callee_id (callee_id),
                KEY idx_call_logs_group_id (group_id),
                CONSTRAINT fk_calls_caller FOREIGN KEY (caller_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_calls_callee FOREIGN KEY (callee_id) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT fk_calls_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    """Reverse the migration."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS call_logs")
    conn.commit()
