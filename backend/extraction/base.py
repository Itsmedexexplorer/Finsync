"""Base interfaces and protocols for VERITY evidence extraction providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.domain.evidence import Evidence
from backend.extraction.result import ExtractionResult


class BaseExtractor(ABC):
    """Abstract interface for all evidence extraction engines (Deterministic & AI)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier of this extraction provider."""
        pass

    @abstractmethod
    def can_extract(self, evidence: Evidence) -> bool:
        """Check whether this extractor is suited to handle the given evidence item."""
        pass

    @abstractmethod
    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """Extract structured financial claims from the given raw evidence."""
        pass
