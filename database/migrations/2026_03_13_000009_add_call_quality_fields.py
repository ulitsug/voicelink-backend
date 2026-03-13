"""Add end_reason and quality_score columns to call_logs table."""


def up(connection):
    cursor = connection.cursor()
    cursor.execute("""
        ALTER TABLE call_logs
        ADD COLUMN end_reason VARCHAR(30) NULL,
        ADD COLUMN quality_score INT NULL
    """)
    connection.commit()


def down(connection):
    cursor = connection.cursor()
    cursor.execute("""
        ALTER TABLE call_logs
        DROP COLUMN end_reason,
        DROP COLUMN quality_score
    """)
    connection.commit()
