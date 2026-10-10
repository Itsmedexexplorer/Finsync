"""Result and status models for the VERITY Extraction Subsystem.

Ensures provider-independent extraction results with explicit confidence metadata,
warnings, error tracking, and strict separation between asserted claims and financial truth.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.claim import Claim


class ExtractionStatus(str, Enum):
    """Status of an extraction operation on an Evidence artifact."""
    SUCCESS = "SUCCESS"                             # Claims extracted with high/acceptable confidence
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"             # Some claims extracted, with ambiguities or warnings
    NO_CLAIMS_FOUND = "NO_CLAIMS_FOUND"             # Evidence contains no financial claims (e.g. casual greeting)
    REQUIRES_VISION_OR_OCR = "REQUIRES_VISION_OR_OCR" # Scanned PDF or image where text extraction requires vision model
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"   # Requested AI provider offline or unconfigured
    EXTRACTION_ERROR = "EXTRACTION_ERROR"           # Malformed input or schema validation failure


class ExtractionWarning(BaseModel):
    """Non-fatal warning encountered during extraction."""
    message: str = Field(..., description="Warning description")
    field: Optional[str] = Field(None, description="The specific field affected (e.g. 'claimed_amount')")
    raw_snippet: Optional[str] = Field(None, description="Raw text snippet that triggered the warning")


class ExtractionResult(BaseModel):
    """Container holding extracted Claim objects alongside provider diagnostics and confidence metrics."""
    evidence_id: str = Field(..., description="ID of the Evidence item from which claims were extracted")
    status: ExtractionStatus = Field(..., description="Extraction outcome")
    claims: List[Claim] = Field(default_factory=list, description="Structured claims extracted from the evidence")
    provider_name: str = Field(default="deterministic", description="Identifier of the extraction engine or model")
    confidence_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Overall extraction confidence score (0.0 to 1.0)"
    )
    warnings: List[ExtractionWarning] = Field(default_factory=list, description="Non-fatal extraction warnings")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during extraction")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific diagnostics (execution time, tokens, model name, etc.)"
    )

    @classmethod
    def create_success(
        cls,
        evidence_id: str,
        claims: List[Claim],
        provider_name: str = "deterministic",
        confidence_score: float = 1.0,
        warnings: Optional[List[ExtractionWarning]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """Helper to create a successful ExtractionResult."""
        status = ExtractionStatus.SUCCESS if claims else ExtractionStatus.NO_CLAIMS_FOUND
        return cls(
            evidence_id=evidence_id,
            status=status,
            claims=claims,
            provider_name=provider_name,
            confidence_score=confidence_score,
            warnings=warnings or [],
            errors=[],
            metadata=metadata or {},
        )

    @classmethod
    def create_failure(
        cls,
        evidence_id: str,
        status: ExtractionStatus,
        error_message: str,
        provider_name: str = "deterministic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """Helper to create a failed ExtractionResult."""
        return cls(
            evidence_id=evidence_id,
            status=status,
            claims=[],
            provider_name=provider_name,
            confidence_score=0.0,
            warnings=[],
            errors=[error_message],
            metadata=metadata or {},
        )
