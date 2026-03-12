"""
Migration: Create Messages Table
Created: 2026-03-13
Description: Creates the messages table for direct and group messaging.
"""


def up(conn):
    """Apply the migration."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                sender_id INT NOT NULL,
                receiver_id INT DEFAULT NULL,
                group_id INT DEFAULT NULL,
                content TEXT DEFAULT NULL,
                encrypted_content TEXT DEFAULT NULL,
                message_type VARCHAR(20) DEFAULT 'text',
                file_url VARCHAR(500) DEFAULT NULL,
                file_name VARCHAR(255) DEFAULT NULL,
                file_size INT DEFAULT NULL,
                is_read TINYINT(1) DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                KEY idx_messages_sender_id (sender_id),
                KEY idx_messages_receiver_id (receiver_id),
                KEY idx_messages_group_id (group_id),
                KEY idx_messages_created_at (created_at),
                CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                CONSTRAINT fk_messages_receiver FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE SET NULL,
                CONSTRAINT fk_messages_group FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
    conn.commit()


def down(conn):
    """Reverse the migration."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS messages")
    conn.commit()
