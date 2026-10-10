"""Deterministic Bank CSV Claim Extractor for VERITY.

Extracts structured financial claims from normalized Bank Statement CSV evidence.
Never performs reconciliation or transaction matching.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from backend.domain.claim import Claim, ClaimStatus, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.extraction.base import BaseExtractor
from backend.extraction.result import ExtractionResult, ExtractionStatus, ExtractionWarning


class BankCSVExtractor(BaseExtractor):
    """Deterministic extractor for Bank CSV row evidence."""

    @property
    def provider_name(self) -> str:
        return "deterministic_bank_csv"

    def can_extract(self, evidence: Evidence) -> bool:
        return (
            evidence.modality == EvidenceModality.BANK_STATEMENT
            and evidence.source_type == EvidenceSourceType.BANK_CSV
        )

    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        if not self.can_extract(evidence):
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.EXTRACTION_ERROR,
                error_message=f"BankCSVExtractor cannot process evidence with modality '{evidence.modality.value}'.",
                provider_name=self.provider_name,
            )

        norm_fields = evidence.metadata.get("normalized_fields", {})
        raw_row = norm_fields or {}

        date_val = raw_row.get("date")
        narration_val = raw_row.get("narration") or ""
        ref_val = raw_row.get("reference")
        credit_val = raw_row.get("credit")
        debit_val = raw_row.get("debit")
        amt_val = raw_row.get("amount")

        # Parse amounts
        parsed_credit = self._clean_numeric_amount(credit_val)
        parsed_debit = self._clean_numeric_amount(debit_val)
        parsed_amt = self._clean_numeric_amount(amt_val)

        claims: List[Claim] = []
        warnings: List[ExtractionWarning] = []

        # Determine direction & payment rail
        payment_method = self._detect_payment_rail(narration_val)
        counterparty_hint = self._extract_counterparty_from_narration(narration_val)
        reference_hint = ref_val or self._extract_reference_from_narration(narration_val)

        # 1. Check Credit (Deposit)
        if parsed_credit is not None and parsed_credit > 0:
            claim_id = f"CLM-CSV-{uuid.uuid4().hex[:8]}"
            c = Claim(
                id=claim_id,
                evidence_id=evidence.id,
                claim_type=ClaimType.PAYMENT_RECEIVED,
                claimed_amount=parsed_credit,
                claimed_date=date_val,
                counterparty_hint=counterparty_hint,
                reference_id_hint=reference_hint,
                payment_method_hint=payment_method,
                confidence=1.0,
                raw_text_snippet=evidence.raw_payload,
                status=ClaimStatus.ASSERTED,
                metadata={"source_row_index": evidence.metadata.get("row_index")},
            )
            claims.append(c)

        # 2. Check Debit (Withdrawal)
        elif parsed_debit is not None and parsed_debit > 0:
            claim_id = f"CLM-CSV-{uuid.uuid4().hex[:8]}"
            c = Claim(
                id=claim_id,
                evidence_id=evidence.id,
                claim_type=ClaimType.PAYMENT_SENT,
                claimed_amount=parsed_debit,
                claimed_date=date_val,
                counterparty_hint=counterparty_hint,
                reference_id_hint=reference_hint,
                payment_method_hint=payment_method,
                confidence=1.0,
                raw_text_snippet=evidence.raw_payload,
                status=ClaimStatus.ASSERTED,
                metadata={"source_row_index": evidence.metadata.get("row_index")},
            )
            claims.append(c)

        # 3. Check generic Amount column
        elif parsed_amt is not None and parsed_amt > 0:
            # Check narration for debit clues (e.g. WDL, DR, PAYMENT TO)
            is_debit = any(k in narration_val.upper() for k in ("WDL", "/DR", "DEBIT", "PAY TO", "PAID TO"))
            claim_type = ClaimType.PAYMENT_SENT if is_debit else ClaimType.PAYMENT_RECEIVED
            
            claim_id = f"CLM-CSV-{uuid.uuid4().hex[:8]}"
            c = Claim(
                id=claim_id,
                evidence_id=evidence.id,
                claim_type=claim_type,
                claimed_amount=parsed_amt,
                claimed_date=date_val,
                counterparty_hint=counterparty_hint,
                reference_id_hint=reference_hint,
                payment_method_hint=payment_method,
                confidence=0.95,
                raw_text_snippet=evidence.raw_payload,
                status=ClaimStatus.ASSERTED,
                metadata={"source_row_index": evidence.metadata.get("row_index")},
            )
            claims.append(c)
        else:
            warnings.append(ExtractionWarning(
                message="CSV row contains zero or unparseable monetary values.",
                raw_snippet=evidence.raw_payload,
            ))

        return ExtractionResult.create_success(
            evidence_id=evidence.id,
            claims=claims,
            provider_name=self.provider_name,
            confidence_score=1.0 if claims else 0.0,
            warnings=warnings,
            metadata={"row_index": evidence.metadata.get("row_index")},
        )

    def _clean_numeric_amount(self, val: Optional[str]) -> Optional[float]:
        """Parse numeric float from formatted string (e.g. '35,000.00', '₹ 12,500')."""
        if not val:
            return None
        cleaned = re.sub(r"[^\d.]", "", str(val).strip())
        if not cleaned:
            return None
        try:
            amt = float(cleaned)
            return round(amt, 2)
        except ValueError:
            return None

    def _detect_payment_rail(self, narration: str) -> Optional[str]:
        """Detect standard Indian payment rails from narration."""
        upper = narration.upper()
        if "UPI" in upper:
            return "UPI"
        if "NEFT" in upper:
            return "NEFT"
        if "RTGS" in upper:
            return "RTGS"
        if "IMPS" in upper:
            return "IMPS"
        if "CHQ" in upper or "CHEQUE" in upper:
            return "CHEQUE"
        if "ATM" in upper or "CASH" in upper:
            return "CASH"
        if "RZP" in upper or "RAZORPAY" in upper or "GATEWAY" in upper:
            return "GATEWAY"
        return None

    def _extract_counterparty_from_narration(self, narration: str) -> Optional[str]:
        """Extract counterparty name segment from Indian bank narrations."""
        if not narration:
            return None
        # e.g. "UPI/408219381920/PAYTO/RAMESH SHARMA/HDFC"
        # or "NEFT/NEFTN26235889012/POOJAPLASTICS/ICICI"
        parts = narration.split("/")
        if len(parts) >= 4:
            # Often the 3rd or 4th element is the counterparty
            for p in parts[2:]:
                p_clean = p.strip()
                if p_clean and not p_clean.isdigit() and len(p_clean) > 2 and p_clean.upper() not in ("PAYTO", "UPI", "NEFT", "IMPS", "VERIFIED"):
                    return p_clean
        return None

    def _extract_reference_from_narration(self, narration: str) -> Optional[str]:
        """Extract UTR / RRN (12 digits) or NEFT reference from narration."""
        if not narration:
            return None
        # UPI 12-digit RRN
        m_rrn = re.search(r"\b\d{12}\b", narration)
        if m_rrn:
            return m_rrn.group(0)
        # NEFT UTR pattern e.g. NEFTN26235889012
        m_neft = re.search(r"\b(?:NEFT|RTGS)[A-Z0-9]{10,18}\b", narration, re.IGNORECASE)
        if m_neft:
            return m_neft.group(0)
        return None
