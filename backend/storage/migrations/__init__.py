"""VERITY Database Migration Runner."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.storage.database import DatabaseConnection

logger = logging.getLogger("verity.storage.migrations")


def run_migrations(conn: DatabaseConnection) -> list[str]:
    """Runs all pending schema migrations in chronological order."""
    applied: list[str] = []

    # Import and apply 0001_initial_schema
    m0001 = importlib.import_module("backend.storage.migrations.0001_initial_schema")
    VERSION = m0001.VERSION
    apply_migration = m0001.apply_migration

    # Check if table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations';"
    )
    has_table = cursor.fetchone() is not None

    already_applied = False
    if has_table:
        cur = conn.execute("SELECT version FROM schema_migrations WHERE version = ?;", (VERSION,))
        already_applied = cur.fetchone() is not None

    if not already_applied:
        logger.info(f"Applying migration: {VERSION}")
        apply_migration(conn)
        applied.append(VERSION)

    return applied
