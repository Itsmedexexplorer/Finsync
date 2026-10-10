"""Pairwise Signal Extraction and Scoring for Financial Claims and Transactions.

Extracts transparent matching signals, detects contradictions, and computes pairwise candidate scores.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import PaymentMethod, Transaction, TransactionDirection
from backend.entity_resolution.normalizer import EntityNormalizer
from backend.transaction_matching.config import MatchConfig


class PairwiseSignalEvaluator:
    """Evaluates multi-signal correlation between a source Claim and a target Transaction."""

    WEIGHT_EXACT_REFERENCE = 1.00
    WEIGHT_EXACT_INVOICE_NUMBER = 1.00
    WEIGHT_EXACT_ENTITY_MATCH = 0.90
    WEIGHT_EXACT_AMOUNT_MATCH = 0.80
    WEIGHT_DATE_PROXIMITY = 0.70
    WEIGHT_PAYMENT_METHOD = 0.60
    WEIGHT_NARRATION_KEYWORD = 0.55
    WEIGHT_PARTIAL_AMOUNT = 0.50

    @classmethod
    def evaluate_pair(
        cls,
        claim: Claim,
        transaction: Transaction,
        claim_entity_id: Optional[str] = None,
        config: Optional[MatchConfig] = None,
    ) -> Tuple[float, List[str], List[str], str]:
        """Calculates match score, positive signals, conflicting signals, and explanation."""
        cfg = config or MatchConfig()
        matched_signals: List[str] = []
        conflicting_signals: List[str] = []
        signal_scores: List[float] = []
        reasons: List[str] = []

        # 1. Direction Compatibility
        # Invoices / Claims for Payment Received align with TransactionDirection.CREDIT
        # Claims for Payment Sent align with TransactionDirection.DEBIT
        if claim.claim_type in (ClaimType.INVOICE_ISSUED, ClaimType.PAYMENT_RECEIVED):
            if transaction.direction != TransactionDirection.CREDIT:
                conflicting_signals.append("MISMATCHED_DIRECTION")
                reasons.append(f"Claim is inflow ({claim.claim_type.value}) but transaction is {transaction.direction.value}.")
        elif claim.claim_type == ClaimType.PAYMENT_SENT:
            if transaction.direction != TransactionDirection.DEBIT:
                # If transaction is credit, conflict unless claim was from counterparty perspective
                pass

        # 2. Entity Compatibility
        txn_entity_id = transaction.origin_entity_id or transaction.destination_entity_id
        if claim_entity_id and txn_entity_id:
            if claim_entity_id == txn_entity_id:
                matched_signals.append("EXACT_ENTITY_MATCH")
                signal_scores.append(cls.WEIGHT_EXACT_ENTITY_MATCH)
                reasons.append(f"Entity ID '{claim_entity_id}' matches on both claim and transaction.")
            else:
                conflicting_signals.append("CONFLICTING_ENTITY")
                reasons.append(f"Claim entity '{claim_entity_id}' conflicts with transaction entity '{txn_entity_id}'.")

        # 3. Reference ID / UTR / RRN / Invoice # Matching
        ref_matched = False
        claim_ref = (claim.reference_id_hint or "").strip()
        txn_ref = (transaction.bank_reference or "").strip()
        narration = (transaction.narration or "").strip()

        if claim_ref:
            # Direct bank reference match
            if txn_ref and cls._normalize_ref(claim_ref) == cls._normalize_ref(txn_ref):
                matched_signals.append("EXACT_REFERENCE")
                signal_scores.append(cls.WEIGHT_EXACT_REFERENCE)
                reasons.append(f"Bank reference / UTR '{claim_ref}' matches exactly.")
                ref_matched = True
            # Reference cited inside narration
            elif narration and cls._normalize_ref(claim_ref) in cls._normalize_ref(narration):
                matched_signals.append("EXACT_REFERENCE_IN_NARRATION")
                signal_scores.append(cls.WEIGHT_EXACT_REFERENCE)
                reasons.append(f"Reference '{claim_ref}' found in transaction narration.")
                ref_matched = True

        # 4. Amount Matching
        if claim.claimed_amount is not None:
            claim_amt = float(claim.claimed_amount)
            txn_amt = float(transaction.amount)

            if abs(claim_amt - txn_amt) <= cfg.amount_tolerance_abs:
                matched_signals.append("EXACT_AMOUNT_MATCH")
                signal_scores.append(cls.WEIGHT_EXACT_AMOUNT_MATCH)
                reasons.append(f"Amounts match exactly (₹{claim_amt:,.2f}).")
            elif txn_amt < claim_amt:
                matched_signals.append("PARTIAL_AMOUNT_MATCH")
                signal_scores.append(cls.WEIGHT_PARTIAL_AMOUNT)
                reasons.append(f"Transaction (₹{txn_amt:,.2f}) is a partial amount of claim (₹{claim_amt:,.2f}).")
            else:
                # Transaction amount is greater than claim amount
                pass

        # 5. Date Proximity
        date_diff = cls._calculate_date_difference(claim.claimed_date, transaction.known_timestamp)
        if date_diff is not None:
            if date_diff <= cfg.date_tolerance_days:
                matched_signals.append("DATE_PROXIMITY")
                signal_scores.append(cls.WEIGHT_DATE_PROXIMITY)
                reasons.append(f"Dates are within {date_diff} day(s) tolerance.")
            elif date_diff > 45:
                conflicting_signals.append("EXTREME_DATE_DRIFT")
                reasons.append(f"Dates differ by {date_diff} days, exceeding realistic settlement window.")

        # 6. Payment Rail Compatibility
        if claim.payment_method_hint and transaction.payment_method:
            if claim.payment_method_hint.upper() == transaction.payment_method.value.upper():
                matched_signals.append("PAYMENT_METHOD_MATCH")
                signal_scores.append(cls.WEIGHT_PAYMENT_METHOD)
                reasons.append(f"Payment rail '{transaction.payment_method.value}' matches.")

        # 7. Narration Counterparty Keyword Match
        if claim.counterparty_hint and narration:
            norm_counterparty = EntityNormalizer.normalize_name(claim.counterparty_hint)
            norm_narration = EntityNormalizer.normalize_name(narration)
            tokens = EntityNormalizer.extract_core_name_tokens(claim.counterparty_hint)
            if tokens and all(t in norm_narration for t in tokens):
                matched_signals.append("NARRATION_KEYWORD_MATCH")
                signal_scores.append(cls.WEIGHT_NARRATION_KEYWORD)
                reasons.append(f"Counterparty name '{claim.counterparty_hint}' identified in bank narration.")

        # Calculate Overall Pairwise Score
        if not signal_scores:
            final_score = 0.0
            explanation = "No matching financial signals identified."
        else:
            # Multi-signal reinforcement
            max_score = max(signal_scores)
            bonus = 0.04 * (len(signal_scores) - 1) if len(signal_scores) > 1 else 0.0
            final_score = min(1.0, max_score + bonus)

            # Penalize heavily if conflicting signals present
            if conflicting_signals:
                final_score = max(0.05, final_score - (0.35 * len(conflicting_signals)))

            explanation = "; ".join(reasons)

        return (round(final_score, 2), matched_signals, conflicting_signals, explanation)

    @classmethod
    def _normalize_ref(cls, ref: str) -> str:
        """Strip formatting, prefixes (UTR, RRN, REF, TXN), and whitespace for comparison."""
        cleaned = re.sub(r"^[\s]*(?:UTR|RRN|REF|TXN|INV)[:\s\-_]*", "", str(ref), flags=re.IGNORECASE)
        return re.sub(r"[\s\-_/]", "", cleaned).upper()

    @classmethod
    def _calculate_date_difference(cls, claim_date_str: Optional[str], txn_datetime: Optional[datetime]) -> Optional[int]:
        """Calculates absolute difference in days between claim date and transaction date."""
        if not claim_date_str or not txn_datetime:
            return None

        claim_dt = cls._parse_date(claim_date_str)
        if not claim_dt:
            return None

        # Compare dates in days
        txn_d = txn_datetime.date() if isinstance(txn_datetime, datetime) else txn_datetime
        diff = abs((claim_dt.date() - txn_d).days)
        return diff

    @classmethod
    def _parse_date(cls, date_str: str) -> Optional[datetime]:
        """Parses various date string formats."""
        cleaned = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        # Check ISO timestamp with time
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except Exception:
            return None
