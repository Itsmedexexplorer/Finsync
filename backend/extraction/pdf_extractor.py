"""PDF Document Claims Extractor for VERITY.

Extracts structured financial claims from text-based PDF invoices and receipts.
Accurately identifies scanned documents and signals REQUIRES_VISION_OR_OCR rather than hallucinating.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from backend.domain.claim import Claim, ClaimStatus, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality
from backend.extraction.base import BaseExtractor
from backend.extraction.document_fields import find_invoice_number, find_parties, find_payment_reference
from backend.extraction.result import ExtractionResult, ExtractionStatus, ExtractionWarning


class PDFDocumentExtractor(BaseExtractor):
    """Extractor for PDF invoices, receipts, and statement evidence."""

    @property
    def provider_name(self) -> str:
        return "deterministic_pdf"

    def can_extract(self, evidence: Evidence) -> bool:
        return (
            evidence.modality in (EvidenceModality.INVOICE, EvidenceModality.RECEIPT)
            or evidence.source_name.lower().endswith(".pdf")
        )

    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        # Check if PDF was flagged as scanned / image-only during ingestion
        if evidence.metadata.get("is_scanned") is True:
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.REQUIRES_VISION_OR_OCR,
                error_message="Document is a scanned image-only PDF without embedded text stream. Requires multimodal vision/OCR extraction.",
                provider_name=self.provider_name,
            )

        raw_text = evidence.raw_payload.strip()
        if not raw_text or raw_text.startswith("[SCANNED_"):
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.REQUIRES_VISION_OR_OCR,
                error_message="No extractable text found in PDF document.",
                provider_name=self.provider_name,
            )

        # Extract Invoice Number
        invoice_number = self._extract_invoice_number(raw_text)

        # Extract Amount
        amount = self._extract_invoice_amount(raw_text)

        # Extract Billed To Party
        parties = find_parties(raw_text)
        counterparty = parties.get("client") or self._extract_counterparty(raw_text)

        # A UTR printed on the document is what the bank statement shows, so it is the
        # reference to match on; the invoice number is kept alongside it.
        payment_reference = find_payment_reference(raw_text)

        # Extract Date
        invoice_date = self._extract_date(raw_text)

        claim_type = (
            ClaimType.PAYMENT_RECEIVED
            if evidence.modality == EvidenceModality.RECEIPT
            else ClaimType.INVOICE_ISSUED
        )

        confidence = 0.95 if amount is not None and invoice_number is not None else 0.80
        claim_id = f"CLM-PDF-{uuid.uuid4().hex[:8]}"

        claim = Claim(
            id=claim_id,
            evidence_id=evidence.id,
            claim_type=claim_type,
            claimed_amount=amount,
            claimed_date=invoice_date,
            counterparty_hint=counterparty,
            reference_id_hint=payment_reference or invoice_number,
            confidence=round(confidence, 2),
            raw_text_snippet=raw_text[:300],
            status=ClaimStatus.ASSERTED,
            metadata={
                "page_count": evidence.metadata.get("page_count", 1),
                **({"invoice_number": invoice_number} if invoice_number else {}),
                **({"payment_reference": payment_reference} if payment_reference else {}),
                **{f"party_{k}": v for k, v in parties.items()},
            },
        )

        warnings: List[ExtractionWarning] = []
        if amount is None:
            warnings.append(ExtractionWarning(
                message="Invoice total amount could not be deterministically resolved from text.",
                field="claimed_amount",
            ))

        return ExtractionResult.create_success(
            evidence_id=evidence.id,
            claims=[claim],
            provider_name=self.provider_name,
            confidence_score=claim.confidence,
            warnings=warnings,
            metadata={
                "invoice_number": invoice_number,
                "amount": amount,
                "counterparty": counterparty,
            },
        )

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice reference identifier e.g. #INV-2026-088 (same line as its label, with a digit)."""
        return find_invoice_number(text)

    def _extract_invoice_amount(self, text: str) -> Optional[float]:
        """Extract total invoice / due amount."""
        # 1. Total Due / Grand Total / Net Amount
        m_tot = re.search(
            r"(?:total\s*due|amount\s*due|grand\s*total|total\s*amount|net\s*payable|total)\s*[:#\s]?(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
            text,
            re.IGNORECASE,
        )
        if m_tot:
            try:
                return round(float(m_tot.group(1).replace(",", "")), 2)
            except ValueError:
                pass

        # 2. General currency pattern in invoice
        m_curr = re.search(r"(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if m_curr:
            try:
                return round(float(m_curr.group(1).replace(",", "")), 2)
            except ValueError:
                pass

        return None

    def _extract_counterparty(self, text: str) -> Optional[str]:
        """Extract 'Billed To' or 'Customer Name' from invoice text."""
        m = re.search(r"(?:billed\s*to|client|customer|invoice\s*to)\s*[:#\s]?\s*([^\n\r|]{3,50})", text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Clean trailing noise
            candidate = re.sub(r"\s*\|\s*.*$", "", candidate)
            return candidate.strip()
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract invoice or due date."""
        m = re.search(r"(?:date|due\s*date|invoice\s*date)\s*[:#\s]?\s*(\d{1,4}[/-]\d{1,2}[/-]\d{2,4})", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None
