"""Deterministic Event Fingerprinting and Blocking Key Generation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


class EventFingerprint:
    """Generates candidate clustering keys for cross-modal deduplication."""

    @classmethod
    def get_content_hash_key(cls, content_hash: str) -> str:
        """Clustering key for cryptographic content duplication."""
        return f"HASH:{content_hash.strip().lower()}"

    @classmethod
    def get_reference_key(cls, reference: Optional[str]) -> Optional[str]:
        """Clustering key based on UTR / RRN / Transaction reference."""
        if not reference:
            return None
        cleaned = re.sub(r"^[\s]*(?:UTR|RRN|REF|TXN|INV)[:\s\-_]*", "", str(reference), flags=re.IGNORECASE)
        norm = re.sub(r"[\s\-_/]", "", cleaned).upper()
        return f"REF:{norm}" if len(norm) >= 4 else None

    @classmethod
    def get_event_cluster_key(
        cls,
        entity_id: Optional[str],
        amount: Optional[float],
        date_str: Optional[str],
        direction: Optional[str] = None,
    ) -> str:
        """Soft candidate clustering key based on entity, amount, date bucket, and direction."""
        ent = entity_id.strip() if entity_id else "UNKNOWN"
        amt = f"{amount:.2f}" if amount is not None else "NONE"
        date_bucket = cls._extract_date_bucket(date_str)
        dir_val = direction.upper() if direction else "CREDIT"
        return f"EAD:{ent}:{amt}:{date_bucket}:{dir_val}"

    @classmethod
    def _extract_date_bucket(cls, date_str: Optional[str]) -> str:
        """Extracts YYYY-MM or YYYY-MM-DD bucket for date proximity grouping."""
        if not date_str:
            return "NODATE"
        cleaned = date_str.strip()
        # ISO format YYYY-MM-DD
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", cleaned)
        if m:
            return m.group(1)
        # DD/MM/YYYY or DD-MM-YYYY
        m_dd = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", cleaned)
        if m_dd:
            d, mth, y = m_dd.group(1).zfill(2), m_dd.group(2).zfill(2), m_dd.group(3)
            if len(y) == 2:
                y = f"20{y}"
            return f"{y}-{mth}-{d}"
        return "NODATE"
