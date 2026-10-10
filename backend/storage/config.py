"""VERITY Storage & Database Configuration (Day 16).

Provides configuration settings for persistent storage, connection pooling,
database timeouts, and query logging.
"""

from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field


class StorageSettings(BaseModel):
    """Configuration settings for database and storage layers."""

    database_url: str = Field(
        default_factory=lambda: os.getenv("VERITY_DATABASE_URL", "sqlite:///data/verity.db"),
        description="Database connection URL (e.g. sqlite:///data/verity.db or postgresql://...)",
    )
    pool_size: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_DATABASE_POOL_SIZE", "10")),
        ge=1,
        le=100,
        description="Maximum number of persistent connections in pool",
    )
    max_overflow: int = Field(
        default_factory=lambda: int(os.getenv("VERITY_DATABASE_MAX_OVERFLOW", "20")),
        ge=0,
        le=100,
        description="Maximum number of overflow connections allowed",
    )
    timeout: float = Field(
        default_factory=lambda: float(os.getenv("VERITY_DATABASE_TIMEOUT", "30.0")),
        gt=0.0,
        description="Connection and lock acquisition timeout in seconds",
    )
    echo: bool = Field(
        default_factory=lambda: os.getenv("VERITY_DATABASE_ECHO", "false").lower() in ("true", "1", "yes"),
        description="Whether to log executed SQL queries for debugging",
    )


def get_storage_settings() -> StorageSettings:
    """Returns singleton-like instance of StorageSettings."""
    return StorageSettings()
