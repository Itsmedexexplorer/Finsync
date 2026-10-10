"""Unified Extraction Service orchestrating deterministic-first claims extraction and AI fallback."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.ai_provider import AIExtractionProvider
from backend.extraction.bank_csv_extractor import BankCSVExtractor
from backend.extraction.base import BaseExtractor
from backend.extraction.pdf_extractor import PDFDocumentExtractor
from backend.extraction.result import ExtractionResult, ExtractionStatus
from backend.extraction.text_extractor import TextClaimExtractor


class ExtractionService:
    """Central extraction service coordinating deterministic parsers and AI models."""

    def __init__(
        self,
        bank_extractor: Optional[BankCSVExtractor] = None,
        text_extractor: Optional[TextClaimExtractor] = None,
        pdf_extractor: Optional[PDFDocumentExtractor] = None,
        ai_provider: Optional[AIExtractionProvider] = None,
    ) -> None:
        self.bank_extractor = bank_extractor or BankCSVExtractor()
        self.text_extractor = text_extractor or TextClaimExtractor()
        self.pdf_extractor = pdf_extractor or PDFDocumentExtractor()
        self.ai_provider = ai_provider or AIExtractionProvider()

    def extract_from_evidence(
        self,
        evidence: Evidence,
        use_ai_fallback: bool = True,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        """Extract structured financial claims from a single Evidence artifact."""
        # 1. Structured Bank Statement CSV (Always deterministic)
        if (
            evidence.modality == EvidenceModality.BANK_STATEMENT
            and evidence.source_type == EvidenceSourceType.BANK_CSV
        ):
            return self.bank_extractor.extract(evidence, context)

        # 2. PDF Document (Text vs Scanned)
        if evidence.source_name.lower().endswith(".pdf"):
            pdf_result = self.pdf_extractor.extract(evidence, context)
            if pdf_result.status == ExtractionStatus.SUCCESS:
                return pdf_result
            if pdf_result.status == ExtractionStatus.REQUIRES_VISION_OR_OCR:
                # If multimodal AI is configured, try it; otherwise return requires vision
                if use_ai_fallback and self.ai_provider.can_extract(evidence):
                    ai_res = self.ai_provider.extract(evidence, context)
                    if ai_res.status != ExtractionStatus.PROVIDER_UNAVAILABLE:
                        return ai_res
                return pdf_result

        # 3. Image / Payment Screenshot
        if evidence.modality == EvidenceModality.PAYMENT_SCREENSHOT:
            if use_ai_fallback and self.ai_provider.can_extract(evidence):
                ai_res = self.ai_provider.extract(evidence, context)
                if ai_res.status != ExtractionStatus.PROVIDER_UNAVAILABLE:
                    return ai_res
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.REQUIRES_VISION_OR_OCR,
                error_message="Image payment screenshot requires vision-capable extraction provider.",
                provider_name="extraction_service",
            )

        # 4. Unstructured Text / Messaging Chat / Vouchers
        text_result = self.text_extractor.extract(evidence, context)
        if text_result.status == ExtractionStatus.SUCCESS:
            return text_result

        # If deterministic text did not find claims or had ambiguity, check AI fallback
        if (
            use_ai_fallback
            and text_result.status == ExtractionStatus.NO_CLAIMS_FOUND
            and self.ai_provider.can_extract(evidence)
        ):
            ai_res = self.ai_provider.extract(evidence, context)
            if ai_res.status == ExtractionStatus.SUCCESS:
                return ai_res

        return text_result

    def extract_from_evidence_batch(
        self,
        evidence_list: List[Evidence],
        use_ai_fallback: bool = True,
    ) -> List[ExtractionResult]:
        """Extract claims across a batch of Evidence objects."""
        return [
            self.extract_from_evidence(ev, use_ai_fallback=use_ai_fallback)
            for ev in evidence_list
        ]
