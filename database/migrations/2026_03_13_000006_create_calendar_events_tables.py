"""
Migration: Create Calendar Events Tables
Created: 2026-03-13
Description: Creates calendar_events and event_participants tables for scheduling.
"""


def up(conn):
    """Apply the migration."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT DEFAULT NULL,
                user_id INT NOT NULL,
                group_id INT DEFAULT NULL,
                event_type VARCHAR(20) DEFAULT 'call',
                scheduled_at DATETIME NOT NULL,
                duration_minutes INT DEFAULT 30,
                reminder_minutes INT DEFAULT 15,
                is_recurring TINYINT(1) DEFAULT 0,
                recurrence_rule VARCHAR(100) DEFAULT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                KEY idx_calendar_events_user_id (user_id),
                CONSTRAINT fk_events_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_events_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS event_participants (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_id INT NOT NULL,
                user_id INT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                KEY idx_event_participants_event_id (event_id),
                KEY idx_event_participants_user_id (user_id),
                UNIQUE KEY uq_event_user (event_id, user_id),
                CONSTRAINT fk_ep_event FOREIGN KEY (event_id) REFERENCES calendar_events(id) ON DELETE CASCADE,
                CONSTRAINT fk_ep_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    """Reverse the migration."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS event_participants")
        cur.execute("DROP TABLE IF EXISTS calendar_events")
    conn.commit()
