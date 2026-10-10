"""Result and error models for the VERITY Evidence Ingestion subsystem.

Enables precise tracking of ingestion success, partial failures, malformed rows,
and unsupported formats without silent data loss.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.evidence import Evidence


class IngestionStatus(str, Enum):
    """Overall status of an ingestion operation."""
    SUCCESS = "SUCCESS"                         # 100% of inputs converted to Evidence
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"         # Some inputs succeeded, some failed
    INVALID_INPUT = "INVALID_INPUT"             # Input is empty, missing, or unreadable
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"   # Modality / extension not supported
    MALFORMED_DATA = "MALFORMED_DATA"           # Data structure failed validation completely


class IngestionError(BaseModel):
    """Represents a specific error encountered during evidence ingestion."""
    source_name: str = Field(..., description="Name of the file, stream, or channel")
    row_index: Optional[int] = Field(None, description="1-indexed row number if applicable (e.g. for CSV)")
    error_type: IngestionStatus = Field(default=IngestionStatus.MALFORMED_DATA, description="Error classification")
    message: str = Field(..., description="Clear explanation of the ingestion failure")
    raw_data: Optional[str] = Field(None, description="The raw offending text snippet or row string")


class IngestionResult(BaseModel):
    """Container holding normalized Evidence objects alongside any errors and diagnostics."""
    status: IngestionStatus = Field(..., description="Overall outcome of the ingestion operation")
    evidence_items: List[Evidence] = Field(default_factory=list, description="Normalized canonical Evidence objects")
    errors: List[IngestionError] = Field(default_factory=list, description="List of failures or malformed inputs")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings encountered")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metrics (counts, execution info)")

    @classmethod
    def create_success(
        cls,
        evidence_items: List[Evidence],
        source_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Helper to create a SUCCESS result."""
        meta = metadata or {}
        meta.setdefault("total_records", len(evidence_items))
        meta.setdefault("successful_records", len(evidence_items))
        meta.setdefault("failed_records", 0)
        return cls(
            status=IngestionStatus.SUCCESS,
            evidence_items=evidence_items,
            errors=[],
            warnings=[],
            metadata=meta,
        )

    @classmethod
    def create_failure(
        cls,
        status: IngestionStatus,
        source_name: str,
        message: str,
        row_index: Optional[int] = None,
        raw_data: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionResult:
        """Helper to create a failed IngestionResult."""
        error = IngestionError(
            source_name=source_name,
            row_index=row_index,
            error_type=status,
            message=message,
            raw_data=raw_data,
        )
        meta = metadata or {}
        meta.setdefault("total_records", 1)
        meta.setdefault("successful_records", 0)
        meta.setdefault("failed_records", 1)
        return cls(
            status=status,
            evidence_items=[],
            errors=[error],
            warnings=[],
            metadata=meta,
        )

    def merge(self, other: IngestionResult) -> IngestionResult:
        """Merge another IngestionResult into this one, recalculating the combined status."""
        combined_evidence = self.evidence_items + other.evidence_items
        combined_errors = self.errors + other.errors
        combined_warnings = self.warnings + other.warnings
        
        # Calculate combined status
        if not combined_evidence and combined_errors:
            combined_status = other.status if self.status == IngestionStatus.SUCCESS else self.status
        elif combined_evidence and not combined_errors:
            combined_status = IngestionStatus.SUCCESS
        elif combined_evidence and combined_errors:
            combined_status = IngestionStatus.PARTIAL_SUCCESS
        else:
            combined_status = IngestionStatus.INVALID_INPUT

        combined_metadata = {**self.metadata, **other.metadata}
        combined_metadata["total_records"] = (
            self.metadata.get("total_records", len(self.evidence_items) + len(self.errors))
            + other.metadata.get("total_records", len(other.evidence_items) + len(other.errors))
        )
        combined_metadata["successful_records"] = len(combined_evidence)
        combined_metadata["failed_records"] = len(combined_errors)

        return IngestionResult(
            status=combined_status,
            evidence_items=combined_evidence,
            errors=combined_errors,
            warnings=combined_warnings,
            metadata=combined_metadata,
        )
