"""Base interfaces and protocols for VERITY evidence ingestion adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.ingestion.result import IngestionResult


class BaseIngestionAdapter(ABC):
    """Abstract interface for all multimodal evidence ingestion adapters."""

    @property
    @abstractmethod
    def supported_modalities(self) -> List[EvidenceModality]:
        """List of Evidence modalities produced by this adapter."""
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """List of file extensions handled by this adapter (e.g. ['.csv'])."""
        pass

    def can_handle(self, file_path: Union[Path, str]) -> bool:
        """Check if this adapter can process the given file based on extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        return ext in self.supported_extensions

    @abstractmethod
    def ingest_file(
        self,
        file_path: Union[Path, str],
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest a file from disk and return normalized Evidence objects or errors."""
        pass

    @abstractmethod
    def ingest_payload(
        self,
        raw_content: Union[str, bytes],
        source_name: str,
        source_type: Optional[EvidenceSourceType] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Ingest raw in-memory content/payload and return normalized Evidence objects or errors."""
        pass
