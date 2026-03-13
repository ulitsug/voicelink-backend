#!/usr/bin/env python3
"""
VoiceLink Migration Manager
============================
A Laravel-like database migration system for the VoiceLink backend.

Usage:
    python migrate.py init              Initialize migration tracking table
    python migrate.py make <name>       Create a new migration file
    python migrate.py migrate           Run all pending migrations
    python migrate.py rollback          Rollback the last batch of migrations
    python migrate.py rollback --steps=N  Rollback N batches
    python migrate.py status            Show migration status
    python migrate.py reset             Rollback ALL migrations then re-run all
    python migrate.py fresh             Drop all tables and re-run all migrations
    python migrate.py seed              Run the database seeder
"""

import os
import sys
import importlib.util
import argparse
from datetime import datetime

import pymysql
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'migrations')

# ─── Database Connection ──────────────────────────────────────────────
def get_connection():
    """Get a raw PyMySQL connection from .env settings."""
    socket_path = os.getenv('DB_SOCKET', '/Applications/MAMP/tmp/mysql/mysql.sock')
    conn_kwargs = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USERNAME', 'root'),
        'password': os.getenv('DB_PASSWORD', 'root'),
        'database': os.getenv('DB_DATABASE', 'py_voip'),
        'charset': 'utf8mb4',
        'autocommit': False,
    }
    # Only add unix_socket if it exists (Unix-like systems)
    if os.path.exists(socket_path):
        conn_kwargs['unix_socket'] = socket_path
    return pymysql.connect(**conn_kwargs)


def get_connection_no_db():
    """Get a connection without selecting a database (for CREATE DATABASE)."""
    socket_path = os.getenv('DB_SOCKET', '/Applications/MAMP/tmp/mysql/mysql.sock')
    conn_kwargs = {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'user': os.getenv('DB_USERNAME', 'root'),
        'password': os.getenv('DB_PASSWORD', 'root'),
        'charset': 'utf8mb4',
        'autocommit': True,
    }
    # Only add unix_socket if it exists (Unix-like systems)
    if os.path.exists(socket_path):
        conn_kwargs['unix_socket'] = socket_path
    return pymysql.connect(**conn_kwargs)


# ─── Migration Table ─────────────────────────────────────────────────
def ensure_migrations_table(conn):
    """Create the migrations tracking table if it doesn't exist."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                migration VARCHAR(255) NOT NULL,
                batch INT NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
    conn.commit()


def get_ran_migrations(conn):
    """Get list of already-executed migration names, ordered."""
    with conn.cursor() as cur:
        cur.execute("SELECT migration FROM migrations ORDER BY batch, id")
        return [row[0] for row in cur.fetchall()]


def get_last_batch(conn):
    """Get the current highest batch number."""
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(batch), 0) FROM migrations")
        return cur.fetchone()[0]


def record_migration(conn, name, batch):
    """Record a migration as executed."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO migrations (migration, batch) VALUES (%s, %s)",
            (name, batch)
        )


def remove_migration_record(conn, name):
    """Remove a migration record (for rollback)."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM migrations WHERE migration = %s", (name,))


# ─── Migration File Discovery ────────────────────────────────────────
def get_migration_files():
    """Get sorted list of migration filenames from the migrations directory."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    files = [
        f[:-3]  # strip .py
        for f in sorted(os.listdir(MIGRATIONS_DIR))
        if f.endswith('.py') and not f.startswith('__')
    ]
    return files


def load_migration_module(name):
    """Dynamically load a migration module by name."""
    filepath = os.path.join(MIGRATIONS_DIR, f'{name}.py')
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ─── Commands ─────────────────────────────────────────────────────────
def cmd_init():
    """Initialize: create database if needed, create migrations table."""
    db_name = os.getenv('DB_DATABASE', 'py_voip')

    # Create database if it doesn't exist
    try:
        conn_no_db = get_connection_no_db()
        with conn_no_db.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn_no_db.close()
        print(f"  Database '{db_name}' ready.")
    except Exception as e:
        print(f"  Warning: Could not create database: {e}")

    # Create migrations table
    conn = get_connection()
    ensure_migrations_table(conn)
    conn.close()
    print("  Migrations table created.")
    print("  Migration system initialized successfully.")


def cmd_make(name):
    """Create a new migration file."""
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y_%m_%d_%H%M%S')
    # Sanitize name
    safe_name = name.lower().replace(' ', '_').replace('-', '_')
    filename = f"{timestamp}_{safe_name}"
    filepath = os.path.join(MIGRATIONS_DIR, f"{filename}.py")

    template = f'''"""
Migration: {name.replace('_', ' ').title()}
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def up(conn):
    """Apply the migration."""
    with conn.cursor() as cur:
        # Example:
        # cur.execute("""
        #     CREATE TABLE example (
        #         id INT AUTO_INCREMENT PRIMARY KEY,
        #         name VARCHAR(100) NOT NULL,
        #         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        # """)
        pass
    conn.commit()


def down(conn):
    """Reverse the migration."""
    with conn.cursor() as cur:
        # Example:
        # cur.execute("DROP TABLE IF EXISTS example")
        pass
    conn.commit()
'''

    with open(filepath, 'w') as f:
        f.write(template)

    print(f"  Created migration: {filename}")
    print(f"  File: database/migrations/{filename}.py")


def cmd_migrate():
    """Run all pending migrations."""
    conn = get_connection()
    ensure_migrations_table(conn)

    ran = get_ran_migrations(conn)
    all_migrations = get_migration_files()
    pending = [m for m in all_migrations if m not in ran]

    if not pending:
        print("  Nothing to migrate.")
        conn.close()
        return

    batch = get_last_batch(conn) + 1
    print(f"  Running migrations (batch {batch})...\n")

    for name in pending:
        try:
            module = load_migration_module(name)
            module.up(conn)
            record_migration(conn, name, batch)
            conn.commit()
            print(f"  [OK] {name}")
        except Exception as e:
            conn.rollback()
            print(f"  [FAIL] {name}: {e}")
            conn.close()
            sys.exit(1)

    print(f"\n  Migrated {len(pending)} migration(s) successfully.")
    conn.close()


def cmd_rollback(steps=1):
    """Rollback the last N batches of migrations."""
    conn = get_connection()
    ensure_migrations_table(conn)

    last_batch = get_last_batch(conn)
    if last_batch == 0:
        print("  Nothing to rollback.")
        conn.close()
        return

    target_batch = max(1, last_batch - steps + 1)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT migration, batch FROM migrations WHERE batch >= %s "
            "ORDER BY batch DESC, id DESC",
            (target_batch,)
        )
        to_rollback = cur.fetchall()

    if not to_rollback:
        print("  Nothing to rollback.")
        conn.close()
        return

    print(f"  Rolling back {len(to_rollback)} migration(s)...\n")

    for (name, batch) in to_rollback:
        try:
            module = load_migration_module(name)
            module.down(conn)
            remove_migration_record(conn, name)
            conn.commit()
            print(f"  [OK] Rolled back: {name}")
        except Exception as e:
            conn.rollback()
            print(f"  [FAIL] {name}: {e}")
            conn.close()
            sys.exit(1)

    print(f"\n  Rollback complete.")
    conn.close()


def cmd_status():
    """Show migration status."""
    conn = get_connection()
    ensure_migrations_table(conn)

    ran = get_ran_migrations(conn)
    all_migrations = get_migration_files()

    # Get batch info
    batch_info = {}
    with conn.cursor() as cur:
        cur.execute("SELECT migration, batch, executed_at FROM migrations ORDER BY batch, id")
        for row in cur.fetchall():
            batch_info[row[0]] = {'batch': row[1], 'executed_at': row[2]}

    conn.close()

    if not all_migrations:
        print("  No migration files found.")
        return

    print(f"\n  {'Migration':<55} {'Status':<12} {'Batch':<8} {'Ran At'}")
    print(f"  {'─' * 55} {'─' * 12} {'─' * 8} {'─' * 20}")

    for m in all_migrations:
        if m in batch_info:
            info = batch_info[m]
            status = 'Ran'
            batch = str(info['batch'])
            ran_at = info['executed_at'].strftime('%Y-%m-%d %H:%M:%S') if info['executed_at'] else ''
        else:
            status = 'Pending'
            batch = ''
            ran_at = ''
        print(f"  {m:<55} {status:<12} {batch:<8} {ran_at}")

    ran_count = len([m for m in all_migrations if m in ran])
    pending_count = len(all_migrations) - ran_count
    print(f"\n  Total: {len(all_migrations)} | Ran: {ran_count} | Pending: {pending_count}")


def cmd_reset():
    """Rollback all migrations then re-run them."""
    conn = get_connection()
    ensure_migrations_table(conn)

    last_batch = get_last_batch(conn)
    conn.close()

    if last_batch > 0:
        print("  Resetting: rolling back all migrations...\n")
        cmd_rollback(steps=last_batch)
        print()

    print("  Re-running all migrations...\n")
    cmd_migrate()


def cmd_fresh():
    """Drop all tables and re-run all migrations."""
    conn = get_connection()
    db_name = os.getenv('DB_DATABASE', 'py_voip')

    print(f"  Dropping all tables in '{db_name}'...\n")

    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
        for table in tables:
            cur.execute(f"DROP TABLE IF EXISTS `{table}`")
            print(f"  Dropped: {table}")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    conn.close()

    print()
    cmd_init()
    print()
    cmd_migrate()


def cmd_seed():
    """Run the database seeder."""
    seeder_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'database', 'seeders', 'seeder.py'
    )
    if not os.path.isfile(seeder_path):
        print("  No seeder found at database/seeders/seeder.py")
        return

    conn = get_connection()
    try:
        spec = importlib.util.spec_from_file_location('seeder', seeder_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.run(conn)
        print("  Database seeded successfully.")
    except Exception as e:
        print(f"  Seeding failed: {e}")
    finally:
        conn.close()


# ─── CLI Entry Point ─────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='VoiceLink Database Migration Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init                  Initialize the migration system
  make <name>           Create a new migration file
  migrate               Run all pending migrations
  rollback              Rollback the last batch (use --steps=N for more)
  status                Show migration status
  reset                 Rollback all, then re-run all migrations
  fresh                 Drop ALL tables, re-run all migrations
  seed                  Run database seeders

Examples:
  python migrate.py init
  python migrate.py make create_users_table
  python migrate.py migrate
  python migrate.py rollback --steps=2
  python migrate.py status
  python migrate.py fresh
        """
    )

    parser.add_argument('command', choices=[
        'init', 'make', 'migrate', 'rollback', 'status', 'reset', 'fresh', 'seed'
    ], help='Migration command to run')
    parser.add_argument('name', nargs='?', help='Migration name (for "make" command)')
    parser.add_argument('--steps', type=int, default=1, help='Number of batches to rollback')

    args = parser.parse_args()

    print()
    print(f"  VoiceLink Migration Manager")
    print(f"  {'─' * 40}")

    if args.command == 'init':
        cmd_init()
    elif args.command == 'make':
        if not args.name:
            print("  Error: 'make' requires a migration name.")
            print("  Usage: python migrate.py make <name>")
            sys.exit(1)
        cmd_make(args.name)
    elif args.command == 'migrate':
        cmd_migrate()
    elif args.command == 'rollback':
        cmd_rollback(steps=args.steps)
    elif args.command == 'status':
        cmd_status()
    elif args.command == 'reset':
        cmd_reset()
    elif args.command == 'fresh':
        cmd_fresh()
    elif args.command == 'seed':
        cmd_seed()

    print()


if __name__ == '__main__':
    main()
