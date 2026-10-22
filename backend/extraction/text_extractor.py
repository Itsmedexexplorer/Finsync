"""Deterministic Text and Multilingual Claim Extractor for VERITY.

Extracts financial assertions, Indian currency amounts, payment rails, and reference IDs
from natural language messages, WhatsApp exports, and multilingual text.
Never hallucinates missing amounts or counterparties.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.domain.claim import Claim, ClaimStatus, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality
from backend.extraction.base import BaseExtractor
from backend.extraction.result import ExtractionResult, ExtractionStatus, ExtractionWarning


class TextClaimExtractor(BaseExtractor):
    """Deterministic extractor for unstructured messages, chat logs, and physical vouchers."""

    @property
    def provider_name(self) -> str:
        return "deterministic_text"

    def can_extract(self, evidence: Evidence) -> bool:
        return evidence.modality in (
            EvidenceModality.MESSAGING_CHAT,
            EvidenceModality.RECEIPT,
            EvidenceModality.CASH_VOUCHER,
            EvidenceModality.INVOICE,
            EvidenceModality.OTHER,
        )

    # Devanagari digit translation mapping: ० -> 0, १ -> 1, etc.
    DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

    # Word numerals in Hindi / Marathi / English with word boundaries
    WORD_PHRASES = [
        ("एक हजार", 1000), ("दोन हजार", 2000), ("वीस हजार", 20000),
        ("बीस हज़ार", 20000), ("बीस हजार", 20000), ("पंद्रह हज़ार", 15000), ("पंद्रह हजार", 15000),
        ("ek hazar", 1000), ("do hazar", 2000), ("bees hazar", 20000), ("pandrah hazar", 15000),
        ("das hazar", 10000), ("paanch hazar", 5000), ("pachas hazar", 50000),
        ("twenty thousand", 20000), ("fifteen thousand", 15000), ("ten thousand", 10000),
        ("twenty five thousand", 25000), ("thirty thousand", 30000),
        ("fifty thousand", 50000), ("one lakh", 100000), ("two lakh", 200000),
    ]

    # Relative date expressions: token → timedelta offset (from reference date)
    RELATIVE_DATE_MAP = {
        # English
        "today": 0,
        "yesterday": -1,
        "tomorrow": 1,
        "day before yesterday": -2,
        "day after tomorrow": 2,
        "last week": -7,
        # Hindi / Hinglish
        "kal": -1,   # Could mean yesterday OR tomorrow; default to yesterday
        "parso": -2, # Day before yesterday (or day after tomorrow)
        "aaj": 0,
    }

    # Weekday name mapping (Monday=0 ... Sunday=6)
    WEEKDAY_NAMES = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
        "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
        # Hindi weekday names
        "somvar": 0, "mangalvar": 1, "budhvar": 2, "guruvar": 3,
        "shukravar": 4, "shanivar": 5, "ravivar": 6,
    }

    def extract(
        self,
        evidence: Evidence,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExtractionResult:
        raw_text = evidence.raw_payload.strip()
        if not raw_text:
            return ExtractionResult.create_failure(
                evidence_id=evidence.id,
                status=ExtractionStatus.NO_CLAIMS_FOUND,
                error_message="Evidence payload is empty.",
                provider_name=self.provider_name,
            )

        # 1. Detect Financial Intent & Claim Type
        claim_type = self._detect_claim_type(raw_text)
        if not claim_type:
            # Not a financial message (e.g. casual conversational greeting)
            return ExtractionResult(
                evidence_id=evidence.id,
                status=ExtractionStatus.NO_CLAIMS_FOUND,
                claims=[],
                provider_name=self.provider_name,
                confidence_score=1.0,
            )

        # 2. Extract Monetary Amount (strictly None if not explicitly stated)
        claimed_amount, amount_warning = self._extract_amount(raw_text)

        # 3. Extract Payment Method
        payment_method = self._extract_payment_method(raw_text)

        # 4. Extract Reference ID (UTR / RRN / Cheque / Invoice #)
        reference_id = self._extract_reference_id(raw_text)

        # 5. Extract Counterparty Hint
        counterparty = self._extract_counterparty(raw_text, evidence.metadata)

        # 6. Extract Date Hint
        date_hint = self._extract_date_hint(raw_text, evidence.metadata, context)

        # Confidence calculation
        confidence = 0.90 if claimed_amount is not None else 0.60
        if reference_id:
            confidence = min(1.0, confidence + 0.05)

        claim_id = f"CLM-TXT-{uuid.uuid4().hex[:8]}"
        claim = Claim(
            id=claim_id,
            evidence_id=evidence.id,
            claim_type=claim_type,
            claimed_amount=claimed_amount,
            claimed_date=date_hint,
            counterparty_hint=counterparty,
            reference_id_hint=reference_id,
            payment_method_hint=payment_method,
            confidence=round(confidence, 2),
            raw_text_snippet=raw_text,
            status=ClaimStatus.ASSERTED,
            metadata={
                "language_hint": evidence.language_hint,
                "sender_metadata": evidence.metadata.get("sender"),
            },
        )

        warnings: List[ExtractionWarning] = []
        if amount_warning:
            warnings.append(ExtractionWarning(
                message=amount_warning,
                field="claimed_amount",
                raw_snippet=raw_text,
            ))

        return ExtractionResult.create_success(
            evidence_id=evidence.id,
            claims=[claim],
            provider_name=self.provider_name,
            confidence_score=claim.confidence,
            warnings=warnings,
            metadata={"extracted_fields": {
                "claim_type": claim_type.value,
                "amount": claimed_amount,
                "payment_method": payment_method,
                "reference_id": reference_id,
            }},
        )

    def _detect_claim_type(self, text: str) -> Optional[ClaimType]:
        """Detect the financial intent from vocabulary and phrasing."""
        lower = text.lower()

        # Cash claims
        if any(k in lower for k in ("cash de diya", "petty cash", "cash diya", "cash in hand", "cash payment", "नकद", "रोख")):
            return ClaimType.CASH_PAYMENT_PROMISE

        # Invoices
        if any(k in lower for k in ("tax invoice", "invoice #", "inv-", "total due", "amount due", "bill amount", "invoice marked paid")):
            return ClaimType.INVOICE_ISSUED

        # Payment Received / Inward
        if any(k in lower for k in (
            "received", "credited", "payment received", "mil gaya", "aagaya", "received rs",
            "received payment", "thanks received", "got the payment"
        )):
            return ClaimType.PAYMENT_RECEIVED

        # Payment Sent / Outward (English, Hinglish, Hindi, Marathi, Tamil, Telugu, Kannada, Bengali)
        if any(k in lower for k in (
            "sent", "transferred", "paid", "gpay kar diya", "bhej diya", "send kiya", "bheja",
            "gpay done", "phonepe done", "bhej dunga", "bheja hai", "transfer ho gaya",
            "transfer ho gaye", "paise transfer", "paisa bheja", "payment kar diya", "payment kiya",
            "payment bheja", "pay kiya", "payment done",
            "भेज दिया", "कर दिए हैं", "कर दिया", "पाठवले", "दिला",
            "paniten", "kalsiddini", "chesanu", "diyechi", "i sent", "transferred rs",
            "payment successful", "kar diye", "kar diya", "kar di hai", "bhej diye", "bhej di",
            "transfer kar", "daal diye", "dal diye"
        )):
            return ClaimType.PAYMENT_SENT

        # Refund claims
        if any(k in lower for k in ("refund", "return", "wapas", "wapsi")):
            return ClaimType.REFUND_REQUESTED

        # Check if generic rupee amount is mentioned along with standard payment rail
        if ("₹" in text or "rs" in lower or "inr" in lower or "gpay" in lower or "phonepe" in lower or "upi" in lower
                or "google pay" in lower or "paytm" in lower or "neft" in lower or "imps" in lower or "utr" in lower):
            return ClaimType.PAYMENT_SENT

        return None

    def _extract_amount(self, text: str) -> Tuple[Optional[float], Optional[str]]:
        """Extract exact numeric rupee amount with support for 'k', 'lakh', 'hazar', and Devanagari.

        Candidates are ranked by how clearly they are stated as money, then by position:
          0. after a total label ("Total Due: Rs. 1,50,000.00", "Amount: ₹8,500")
          1. marked as money (₹ / Rs / INR, 20k, 1.5 lakh, 15 hazar, 25000/-, word numerals)
          2. comma-grouped numbers (35,000 · 1,25,000)
          3. bare numbers, skipping ones that are part of an identifier (INV-1058, #1058, A77B)
        Within the best rank, the earliest stated amount wins.
        """
        # 1. Convert Devanagari digits to standard digits
        normalized_text = text.translate(self.DEVANAGARI_DIGITS)
        candidates: List[Tuple[int, float]] = []
        ranked: List[Tuple[int, int, float]] = []  # (rank, position, amount)

        # 1b. Amounts right after a total / amount label
        for m_tot in re.finditer(
            r"(?:total\s*due|amount\s*due|grand\s*total|total\s*amount|net\s*payable|amount(?:\s*(?:paid|received))?)"
            r"\s*[:\-]?\s*(?:₹|Rs\.?|INR)?\s*(?P<amt>\d+(?:,\d+)*(?:\.\d{1,2})?)",
            normalized_text,
            re.IGNORECASE,
        ):
            try:
                ranked.append((0, m_tot.start(), round(float(m_tot.group("amt").replace(",", "")), 2)))
            except ValueError:
                pass

        # 2. Check full phrase word numerals
        for phrase, val in self.WORD_PHRASES:
            idx = normalized_text.lower().find(phrase)
            if idx != -1:
                candidates.append((idx, float(val)))
            elif phrase in text:
                idx2 = text.find(phrase)
                if idx2 != -1:
                    candidates.append((idx2, float(val)))

        # 3. Check explicit currency markers: ₹ 35,000.00 / Rs. 18,500 / INR 25000
        for m_curr in re.finditer(r"(?:₹|Rs\.?|INR)\s*(?P<amt>\d+(?:,\d+)*(?:\.\d{1,2})?)", normalized_text, re.IGNORECASE):
            cleaned = m_curr.group("amt").replace(",", "")
            try:
                candidates.append((m_curr.start(), round(float(cleaned), 2)))
            except ValueError:
                pass

        # 4. Check 'k' suffix e.g. "20k", "35.5k", "20 K"
        for m_k in re.finditer(r"\b(?P<num>\d+(?:\.\d+)?)\s*[kK]\b", normalized_text):
            try:
                base_num = float(m_k.group("num"))
                candidates.append((m_k.start(), round(base_num * 1000.0, 2)))
            except ValueError:
                pass

        # 5. Check 'lakh' / 'lac' / 'L' suffix e.g. "1.5 lakh", "2 lac", "1.5L"
        for m_lakh in re.finditer(r"\b(?P<num>\d+(?:\.\d+)?)\s*(?:lakh|lac|lacs|lakhs|L)\b", normalized_text, re.IGNORECASE):
            try:
                base_num = float(m_lakh.group("num"))
                candidates.append((m_lakh.start(), round(base_num * 100000.0, 2)))
            except ValueError:
                pass

        # 6. Check 'hazar' / 'हजार' e.g. "20 hazar", "15 हजार"
        for m_hazar in re.finditer(r"\b(?P<num>\d+(?:\.\d+)?)\s*(?:hazar|hazaar|हजार|हज़ार|हजारो)\b", normalized_text, re.IGNORECASE):
            try:
                base_num = float(m_hazar.group("num"))
                candidates.append((m_hazar.start(), round(base_num * 1000.0, 2)))
            except ValueError:
                pass

        # 7. Check trailing '/-' format e.g. "25000/-" or "18,500/-"
        for m_slash in re.finditer(r"\b(?P<amt>\d+(?:,\d+)*)\s*/-", normalized_text):
            cleaned = m_slash.group("amt").replace(",", "")
            try:
                candidates.append((m_slash.start(), round(float(cleaned), 2)))
            except ValueError:
                pass

        ranked.extend((1, pos, amt) for pos, amt in candidates)

        # 8. Check standalone comma-formatted numbers e.g. "35,000" or "1,25,000"
        for m_comma in re.finditer(r"\b(?P<amt>\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?)\b", normalized_text):
            if self._is_part_of_identifier(normalized_text, m_comma.start(), m_comma.end()):
                continue
            cleaned = m_comma.group("amt").replace(",", "")
            try:
                ranked.append((2, m_comma.start(), round(float(cleaned), 2)))
            except ValueError:
                pass

        # 9. Check standalone plain integers (3 to 8 digits) that are not reference numbers (e.g. 12500, 22000)
        for m_num in re.finditer(r"\b\d{3,8}(?:\.\d{2})?\b", normalized_text):
            tok = m_num.group(0)
            if self._is_part_of_identifier(normalized_text, m_num.start(), m_num.end()):
                continue
            if not (len(tok) == 4 and tok.startswith("202")) and not (len(tok) == 4 and tok.startswith("19")):  # Skip years
                try:
                    amt = float(tok)
                    if amt >= 100.0:
                        ranked.append((3, m_num.start(), round(amt, 2)))
                except ValueError:
                    pass

        if ranked:
            # Most clearly stated money first, then the earliest position
            ranked.sort(key=lambda c: (c[0], c[1]))
            return ranked[0][2], None

        # 10. If text indicates payment was sent/received without explicit amount e.g. "I sent the money."
        return None, "No explicit monetary amount found in text evidence (amount is unknown)."

    @staticmethod
    def _is_part_of_identifier(text: str, start: int, end: int) -> bool:
        """True for digits glued to letters or ID marks, e.g. INV-1058, #1058, A77B, 1058/26."""
        before = text[start - 1] if start > 0 else ""
        after = text[end] if end < len(text) else ""
        if before.isalpha() or before in "#_/":
            return True
        if before == "-" and start > 1 and text[start - 2].isalnum():
            return True
        return after.isalpha() or after in "_/" or (after == "-" and end + 1 < len(text) and text[end + 1].isalnum())

    def _extract_payment_method(self, text: str) -> Optional[str]:
        """Identify payment rail mentioned in natural language text."""
        lower = text.lower()
        if "gpay" in lower or "google pay" in lower:
            return "UPI"
        if "phonepe" in lower:
            return "UPI"
        if "paytm" in lower:
            return "UPI"
        if "bhim" in lower or "upi" in lower:
            return "UPI"
        if "neft" in lower:
            return "NEFT"
        if "rtgs" in lower:
            return "RTGS"
        if "imps" in lower:
            return "IMPS"
        if "cash" in lower:
            return "CASH"
        if "cheque" in lower or "chq" in lower:
            return "CHEQUE"
        return None

    def _extract_reference_id(self, text: str) -> Optional[str]:
        """Extract UTR, RRN, or Invoice reference numbers from text."""
        # 1. Explicit labeled UTR/Ref e.g. "ref: 408219381920", "UTR 408219381920", "RRN: 408219381920"
        m_ref = re.search(r"(?:ref(?:erence)?(?:\s*no\.?)?|utr|rrn|txn\s*id)\s*[:#-]?\s*([A-Za-z0-9_-]{6,24})", text, re.IGNORECASE)
        if m_ref:
            return m_ref.group(1).strip()

        # 2. Standalone 12-digit UPI RRN
        m_rrn = re.search(r"\b\d{12}\b", text)
        if m_rrn:
            return m_rrn.group(0)

        # 3. Invoice Number e.g. "INV-2026-042"
        m_inv = re.search(r"\b(?:INV|BILL)[-_A-Z0-9]{4,16}\b", text, re.IGNORECASE)
        if m_inv:
            return m_inv.group(0)

        return None

    def _extract_counterparty(self, text: str, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract party hint from metadata or phrases like 'Paid to: Rohit' or 'from Rahul'."""
        if metadata.get("sender"):
            return metadata["sender"]

        # Search for "Paid to: Name" or "from Name"
        m = re.search(r"(?:received from|paid to|sent to|billed to|from)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            # Exclude stop words
            if candidate.lower() not in ("your account", "bank", "gpay", "phonepe", "upi", "via", "using", "today", "yesterday"):
                # Clean trailing tokens like 'via' or 'on'
                candidate = re.sub(r"\s+(?:via|on|ref|using|with|by).*$", "", candidate, flags=re.IGNORECASE).strip()
                return candidate

        return None

    def _extract_date_hint(
        self,
        text: str,
        metadata: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Extract date from metadata timestamp, natural text, or relative expressions.

        Uses reference_timestamp from context for relative date resolution.
        If no reference timestamp is available, relative dates are preserved as-is
        with an 'uncertain' marker.
        """
        if metadata.get("timestamp_hint"):
            return str(metadata["timestamp_hint"])

        # Check ISO format YYYY-MM-DD
        m_iso = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        if m_iso:
            return m_iso.group(0)

        # Check DD/MM/YYYY or DD-MM-YYYY
        m_dd = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text)
        if m_dd:
            return m_dd.group(0)

        # Attempt relative date resolution
        resolved = self._resolve_relative_date(text, context)
        if resolved:
            return resolved

        return None

    def _resolve_relative_date(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Resolve relative date expressions against a reference timestamp.

        If reference_timestamp is not provided in context, preserves the raw
        expression and marks it as uncertain.
        """
        lower = text.lower()

        # Check for weekday names first
        for day_name, day_num in self.WEEKDAY_NAMES.items():
            if day_name in lower:
                ref_date = self._get_reference_date(context)
                if ref_date:
                    # Find the most recent past occurrence of this weekday
                    days_back = (ref_date.weekday() - day_num) % 7
                    if days_back == 0:
                        days_back = 7  # Assume last week if same day
                    resolved = ref_date - timedelta(days=days_back)
                    return resolved.isoformat()
                return f"{day_name} [date_uncertain]"

        # Check relative date tokens
        for token, offset in self.RELATIVE_DATE_MAP.items():
            if token in lower:
                ref_date = self._get_reference_date(context)
                if ref_date:
                    resolved = ref_date + timedelta(days=offset)
                    return resolved.isoformat()
                return f"{token} [date_uncertain]"

        return None

    @staticmethod
    def _get_reference_date(context: Optional[Dict[str, Any]] = None) -> Optional[date]:
        """Extract reference date from context, or return None.

        Does NOT default to current date — relative dates without explicit
        reference remain uncertain.
        """
        if not context:
            return None
        ref_ts = context.get("reference_timestamp")
        if ref_ts is None:
            return None
        if isinstance(ref_ts, datetime):
            return ref_ts.date()
        if isinstance(ref_ts, date):
            return ref_ts
        if isinstance(ref_ts, str):
            try:
                return datetime.fromisoformat(ref_ts).date()
            except (ValueError, TypeError):
                return None
        return None
