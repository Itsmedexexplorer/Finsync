"""Deduplication subsystem for VERITY."""

from backend.deduplication.base import BaseDeduplicator, DuplicateGroup
from backend.deduplication.config import DeduplicationConfig
from backend.deduplication.engine import DeduplicationEngine
from backend.deduplication.fingerprint import EventFingerprint
from backend.deduplication.result import (
    DeduplicationGroup,
    DeduplicationResult,
    DeduplicationStatus,
)
from backend.deduplication.service import DeduplicationService
from backend.deduplication.signals import DeduplicationSignalEvaluator

__all__ = [
    "BaseDeduplicator",
    "DuplicateGroup",
    "DeduplicationConfig",
    "DeduplicationGroup",
    "DeduplicationResult",
    "DeduplicationStatus",
    "EventFingerprint",
    "DeduplicationSignalEvaluator",
    "DeduplicationEngine",
    "DeduplicationService",
]
