"""Add end_reason and quality_score columns to call_logs table."""


def up(conn):
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE call_logs
        ADD COLUMN end_reason VARCHAR(30) NULL,
        ADD COLUMN quality_score INT NULL
    """)
    conn.commit()


def down(conn):
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE call_logs
        DROP COLUMN end_reason,
        DROP COLUMN quality_score
    """)
    conn.commit()
