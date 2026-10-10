"""Contradiction Detection subsystem for VERITY."""

from backend.contradiction_detection.base import BaseContradictionDetector
from backend.contradiction_detection.config import ContradictionConfig
from backend.contradiction_detection.detector import ContradictionDetector
from backend.contradiction_detection.result import ContradictionResult
from backend.contradiction_detection.rules import ContradictionRuleEngine
from backend.contradiction_detection.service import ContradictionDetectionService

__all__ = [
    "BaseContradictionDetector",
    "ContradictionConfig",
    "ContradictionDetector",
    "ContradictionResult",
    "ContradictionRuleEngine",
    "ContradictionDetectionService",
]
