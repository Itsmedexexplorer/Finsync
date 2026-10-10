"""Multi-Signal Cross-Modal Deduplication and Conflict Evaluator."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.deduplication.config import DeduplicationConfig
from backend.deduplication.fingerprint import EventFingerprint


class DeduplicationSignalEvaluator:
    """Evaluates cross-modal correlation and detects contradictions between evidence items."""

    WEIGHT_CONTENT_HASH = 1.00
    WEIGHT_EXACT_REFERENCE = 1.00
    WEIGHT_MATCH_RELATIONSHIP = 0.95
    WEIGHT_ENTITY_AMOUNT_DATE = 0.90
    WEIGHT_PAYMENT_RAIL = 0.75
    WEIGHT_NARRATION_KEYWORD = 0.60

    @classmethod
    def evaluate_correlation(
        cls,
        ref_a: Optional[str],
        ref_b: Optional[str],
        amt_a: Optional[float],
        amt_b: Optional[float],
        ent_a: Optional[str],
        ent_b: Optional[str],
        date_a: Optional[str],
        date_b: Optional[str],
        hash_a: Optional[str] = None,
        hash_b: Optional[str] = None,
        config: Optional[DeduplicationConfig] = None,
    ) -> Tuple[float, List[str], List[str], str]:
        """Computes correlation score, matched signals, conflicting signals, and explanation."""
        cfg = config or DeduplicationConfig()
        matched_signals: List[str] = []
        conflicting_signals: List[str] = []
        signal_scores: List[float] = []
        reasons: List[str] = []

        # 1. Cryptographic Content Hash Match
        if hash_a and hash_b and hash_a.strip().lower() == hash_b.strip().lower():
            matched_signals.append("EXACT_CONTENT_HASH")
            signal_scores.append(cls.WEIGHT_CONTENT_HASH)
            reasons.append("Identical SHA-256 payload hash (exact content duplicate).")
            return (1.00, matched_signals, [], "Cryptographic content duplicate.")

        # 2. Reference Match / Conflict (UTR / RRN)
        key_ref_a = EventFingerprint.get_reference_key(ref_a)
        key_ref_b = EventFingerprint.get_reference_key(ref_b)

        if key_ref_a and key_ref_b:
            if key_ref_a == key_ref_b:
                matched_signals.append("EXACT_REFERENCE")
                signal_scores.append(cls.WEIGHT_EXACT_REFERENCE)
                reasons.append(f"Matching banking reference / UTR '{ref_a}'.")
            else:
                conflicting_signals.append("CONFLICTING_REFERENCE")
                reasons.append(f"Explicit reference mismatch: '{ref_a}' vs '{ref_b}'.")

        # 3. Amount Match / Conflict
        if amt_a is not None and amt_b is not None:
            if abs(amt_a - amt_b) <= cfg.amount_tolerance_abs:
                matched_signals.append("EXACT_AMOUNT_MATCH")
                signal_scores.append(0.80)
                reasons.append(f"Exact amount alignment (₹{amt_a:,.2f}).")
            else:
                # If references matched but amounts differ -> Critical Contradiction!
                if key_ref_a and key_ref_b and key_ref_a == key_ref_b:
                    conflicting_signals.append("CONFLICTING_AMOUNT")
                    reasons.append(f"Same reference '{ref_a}' but conflicting amounts: ₹{amt_a:,.2f} vs ₹{amt_b:,.2f}.")

        # 4. Entity Match / Conflict
        if ent_a and ent_b:
            if ent_a == ent_b:
                matched_signals.append("EXACT_ENTITY_MATCH")
                signal_scores.append(0.85)
                reasons.append(f"Corroborating entity identity '{ent_a}'.")
            else:
                conflicting_signals.append("CONFLICTING_ENTITY")
                reasons.append(f"Conflicting entity identities: '{ent_a}' vs '{ent_b}'.")

        # 5. Date Alignment
        bucket_a = EventFingerprint._extract_date_bucket(date_a)
        bucket_b = EventFingerprint._extract_date_bucket(date_b)
        if bucket_a != "NODATE" and bucket_b != "NODATE":
            if bucket_a == bucket_b:
                matched_signals.append("SAME_DATE_BUCKET")
                signal_scores.append(0.70)
                reasons.append(f"Same settlement date ({bucket_a}).")

        # Calculate Overall Correlation Score
        if not signal_scores:
            final_score = 0.0
            explanation = "No cross-modal correlation signals found."
        else:
            max_score = max(signal_scores)
            bonus = 0.04 * (len(signal_scores) - 1) if len(signal_scores) > 1 else 0.0
            final_score = min(1.0, max_score + bonus)

            # Heavily penalize conflicts
            if conflicting_signals:
                final_score = max(0.10, final_score - (0.35 * len(conflicting_signals)))

            explanation = "; ".join(reasons)

        return (round(final_score, 2), matched_signals, conflicting_signals, explanation)
