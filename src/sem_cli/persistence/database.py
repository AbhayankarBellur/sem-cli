"""SQLite connection management and schema initializations."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """Return an open SQLite connection with foreign keys enabled and row_factory configured."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def initialize_database(db_path: Path) -> None:
    """Initialize SQLite database with schema tables if not present."""
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    sql_script = schema_path.read_text(encoding="utf-8")
    with get_db_connection(db_path) as conn:
        conn.executescript(sql_script)
        # Check migration version
        row = conn.execute("SELECT version FROM schema_migrations WHERE version = 1").fetchone()
        if not row:
            conn.execute("INSERT INTO schema_migrations (version) VALUES (1)")
        conn.commit()
