"""Deterministic Normalization for Indian Entity Names, Phone Numbers, UPI VPAs, and Tax IDs.

Prepares identifiers for fair comparison without altering underlying identity semantics.
"""

from __future__ import annotations

import re
from typing import List, Optional, Set, Tuple


class EntityNormalizer:
    """Normalizes names, Indian phone numbers, UPI VPAs, and official tax identifiers."""

    # Common prefixes, titles, and legal entity suffixes in Indian business
    NAME_PREFIXES = {
        "m/s", "ms", "dr", "mr", "mrs", "shri", "smt", "prof"
    }
    NAME_SUFFIXES = {
        "bhai", "ji", "sir", "madam", "bro", "pvt", "ltd", "private", "limited",
        "llp", "co", "corp", "corporation", "inc", "enterprises", "enterprise",
        "traders", "trading", "solutions", "services", "technologies", "tech",
        "studio", "associates", "agency", "store", "stores"
    }

    # Stop words for token matching
    STOP_WORDS = NAME_PREFIXES | NAME_SUFFIXES | {"and", "&", "the", "of", "in", "for"}

    @classmethod
    def normalize_name(cls, name: Optional[str]) -> str:
        """Standardizes a name for comparison: lowercase, remove punctuation, strip common noise words."""
        if not name:
            return ""

        text = str(name).strip().lower()
        
        # Normalize common M/s or M/s. prefix before punctuation stripping
        text = re.sub(r"^m\s*/\s*s\.?\s+", "", text)
        
        # Replace hyphens/underscores/slashes with spaces
        text = re.sub(r"[-_/\\.,&]", " ", text)
        
        # Remove unwanted punctuation
        text = re.sub(r"[^\w\s]", "", text)
        
        # Split tokens
        tokens = [t for t in text.split() if t]
        if not tokens:
            return ""

        # Remove leading prefix if present (e.g. 'dr', 'shri', 'ms')
        if len(tokens) > 1 and tokens[0] in cls.NAME_PREFIXES:
            tokens = tokens[1:]

        # Remove trailing suffix if present (e.g. 'bhai', 'ji')
        if len(tokens) > 1 and tokens[-1] in ("bhai", "ji", "sir"):
            tokens = tokens[:-1]

        return " ".join(tokens)

    @classmethod
    def extract_core_name_tokens(cls, name: Optional[str]) -> List[str]:
        """Extract significant content tokens from an entity name, omitting common corporate suffixes."""
        normalized = cls.normalize_name(name)
        if not normalized:
            return []
        
        tokens = normalized.split()
        core_tokens = [t for t in tokens if t not in cls.STOP_WORDS and len(t) > 1]
        return core_tokens if core_tokens else tokens

    @classmethod
    def normalize_phone(cls, phone: Optional[str]) -> Optional[str]:
        """Normalize Indian phone numbers to canonical 10-digit format (and validate)."""
        if not phone:
            return None

        # Extract only digits
        digits = "".join(filter(str.isdigit, str(phone)))
        if not digits:
            return None

        # Handle 12-digit format with country code: 919876543210 -> 9876543210
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        # Handle 11-digit format with leading zero: 09876543210 -> 9876543210
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]

        # Standard Indian mobile numbers are 10 digits starting with 6, 7, 8, or 9
        if len(digits) == 10 and digits[0] in "6789":
            return digits
        
        # Fallback if valid 10 digits
        if len(digits) == 10:
            return digits

        return None

    @classmethod
    def normalize_upi_vpa(cls, upi_vpa: Optional[str]) -> Optional[str]:
        """Normalize Virtual Payment Address (e.g. 'user@okhdfcbank')."""
        if not upi_vpa:
            return None

        cleaned = str(upi_vpa).strip().lower()
        if "@" in cleaned and len(cleaned) >= 5:
            # Check basic structure: handle@bank
            parts = cleaned.split("@")
            if len(parts) == 2 and parts[0] and parts[1]:
                return cleaned
        return None

    @classmethod
    def normalize_tax_id(cls, tax_id: Optional[str]) -> Optional[str]:
        """Normalize GSTIN (15 chars) or PAN (10 chars)."""
        if not tax_id:
            return None

        cleaned = re.sub(r"[^A-Za-z0-9]", "", str(tax_id).strip().upper())
        # GSTIN: 15 alphanumeric characters
        if len(cleaned) == 15:
            return cleaned
        # PAN: 10 alphanumeric characters (5 letters, 4 digits, 1 letter)
        if len(cleaned) == 10:
            return cleaned
        return cleaned if cleaned else None

    @classmethod
    def is_initials_match(cls, name_a: str, name_b: str) -> bool:
        """Check if one name is an initial variation of the other (e.g. 'R Kumar' <-> 'Rahul Kumar')."""
        tokens_a = [t for t in cls.normalize_name(name_a).split() if t]
        tokens_b = [t for t in cls.normalize_name(name_b).split() if t]

        if not tokens_a or not tokens_b:
            return False

        # If both are multi-token names and the last names match exactly
        if len(tokens_a) >= 2 and len(tokens_b) >= 2:
            if tokens_a[-1] == tokens_b[-1]:
                # Check if first token of one is the initial of the other
                first_a, first_b = tokens_a[0], tokens_b[0]
                if (len(first_a) == 1 and first_b.startswith(first_a)) or (len(first_b) == 1 and first_a.startswith(first_b)):
                    return True

        return False
