"""Deterministic Contradiction Rules for VERITY.

Evaluates explicit financial disagreements while preventing false positives.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from backend.contradiction_detection.config import ContradictionConfig
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType


class ContradictionRuleEngine:
    """Evaluates deterministic contradiction rules across financial artifacts."""

    @classmethod
    def check_amount_discrepancy(
        cls,
        claim: Claim,
        transaction: Transaction,
        match_relationship: Optional[MatchRelationship] = None,
        config: Optional[ContradictionConfig] = None,
    ) -> Optional[Discrepancy]:
        """RULE_AMOUNT_001: Flags amount discrepancy unless justified by partial payment."""
        cfg = config or ContradictionConfig()
        if claim.claimed_amount is None:
            # Missing amount is NOT a contradiction!
            return None

        # If MatchRelationship identifies this as a valid PARTIAL, MANY_TO_ONE, or ONE_TO_MANY, do NOT flag AMOUNT_MISMATCH!
        if match_relationship and match_relationship.relationship_type in (
            MatchRelationshipType.PARTIAL,
            MatchRelationshipType.MANY_TO_ONE,
            MatchRelationshipType.ONE_TO_MANY,
        ):
            return None

        c_amt = float(claim.claimed_amount)
        t_amt = float(transaction.amount)

        if abs(c_amt - t_amt) > cfg.amount_tolerance_abs:
            disc_id = f"DISC-AMT-{uuid.uuid4().hex[:8]}"
            return Discrepancy(
                id=disc_id,
                discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
                severity=DiscrepancySeverity.ERROR,
                message=f"Amount mismatch: Claimed ₹{c_amt:,.2f} but bank recorded ₹{t_amt:,.2f}.",
                involved_evidence_ids=[claim.evidence_id] + transaction.evidence_ids,
                involved_claim_ids=[claim.id],
                involved_transaction_ids=[transaction.id],
                expected_value=f"{c_amt:.2f}",
                observed_value=f"{t_amt:.2f}",
            )
        return None

    @classmethod
    def check_reference_discrepancy(
        cls,
        ref_a: Optional[str],
        ref_b: Optional[str],
        ev_ids: Optional[List[str]] = None,
        claim_ids: Optional[List[str]] = None,
        txn_ids: Optional[List[str]] = None,
    ) -> Optional[Discrepancy]:
        """RULE_REF_001: Flags conflicting explicit reference / UTR numbers."""
        if not ref_a or not ref_b:
            return None

        norm_a = cls._normalize_ref(ref_a)
        norm_b = cls._normalize_ref(ref_b)

        if norm_a and norm_b and norm_a != norm_b:
            disc_id = f"DISC-REF-{uuid.uuid4().hex[:8]}"
            return Discrepancy(
                id=disc_id,
                discrepancy_type=DiscrepancyType.REFERENCE_MISMATCH,
                severity=DiscrepancySeverity.ERROR,
                message=f"Reference ID mismatch: '{ref_a}' vs '{ref_b}'.",
                involved_evidence_ids=ev_ids or [],
                involved_claim_ids=claim_ids or [],
                involved_transaction_ids=txn_ids or [],
                expected_value=str(ref_a),
                observed_value=str(ref_b),
            )
        return None

    @classmethod
    def check_entity_discrepancy(
        cls,
        entity_a: Optional[str],
        entity_b: Optional[str],
        ev_ids: Optional[List[str]] = None,
        claim_ids: Optional[List[str]] = None,
        txn_ids: Optional[List[str]] = None,
    ) -> Optional[Discrepancy]:
        """RULE_ENTITY_001: Flags conflicting entity identities in the same event context."""
        if not entity_a or not entity_b:
            return None

        if entity_a.strip() != entity_b.strip():
            disc_id = f"DISC-ENT-{uuid.uuid4().hex[:8]}"
            return Discrepancy(
                id=disc_id,
                discrepancy_type=DiscrepancyType.ENTITY_MISMATCH,
                severity=DiscrepancySeverity.CRITICAL,
                message=f"Counterparty identity contradiction: Entity '{entity_a}' conflicts with '{entity_b}'.",
                involved_evidence_ids=ev_ids or [],
                involved_claim_ids=claim_ids or [],
                involved_transaction_ids=txn_ids or [],
                expected_value=entity_a,
                observed_value=entity_b,
            )
        return None

    @classmethod
    def check_date_discrepancy(
        cls,
        date_a_str: Optional[str],
        date_b_dt: Optional[datetime],
        ev_ids: Optional[List[str]] = None,
        claim_ids: Optional[List[str]] = None,
        txn_ids: Optional[List[str]] = None,
        config: Optional[ContradictionConfig] = None,
    ) -> Optional[Discrepancy]:
        """RULE_DATE_001: Flags extreme date drift exceeding threshold."""
        cfg = config or ContradictionConfig()
        if not date_a_str or not date_b_dt:
            return None

        parsed_a = cls._parse_date(date_a_str)
        if not parsed_a:
            return None

        txn_d = date_b_dt.date() if isinstance(date_b_dt, datetime) else date_b_dt
        diff_days = abs((parsed_a.date() - txn_d).days)

        if diff_days > cfg.max_acceptable_date_drift_days:
            disc_id = f"DISC-DAT-{uuid.uuid4().hex[:8]}"
            return Discrepancy(
                id=disc_id,
                discrepancy_type=DiscrepancyType.DATE_MISMATCH,
                severity=DiscrepancySeverity.WARNING,
                message=f"Settlement date drift of {diff_days} days exceeds acceptable threshold ({cfg.max_acceptable_date_drift_days} days).",
                involved_evidence_ids=ev_ids or [],
                involved_claim_ids=claim_ids or [],
                involved_transaction_ids=txn_ids or [],
                expected_value=date_a_str,
                observed_value=str(txn_d),
            )
        return None

    @classmethod
    def check_conflicting_claims(
        cls,
        claims: List[Claim],
    ) -> List[Discrepancy]:
        """RULE_CLAIM_001: Flags contradictory assertions within the same event context."""
        discrepancies: List[Discrepancy] = []
        if len(claims) < 2:
            return discrepancies

        for i in range(len(claims)):
            for j in range(i + 1, len(claims)):
                c1 = claims[i]
                c2 = claims[j]
                # Compare stated amounts
                if c1.claimed_amount is not None and c2.claimed_amount is not None:
                    if abs(c1.claimed_amount - c2.claimed_amount) > 0.0:
                        disc_id = f"DISC-CLM-{uuid.uuid4().hex[:8]}"
                        discrepancies.append(Discrepancy(
                            id=disc_id,
                            discrepancy_type=DiscrepancyType.CONFLICTING_CLAIMS,
                            severity=DiscrepancySeverity.ERROR,
                            message=f"Conflicting claim amounts in same context: ₹{c1.claimed_amount:,.2f} vs ₹{c2.claimed_amount:,.2f}.",
                            involved_evidence_ids=[c1.evidence_id, c2.evidence_id],
                            involved_claim_ids=[c1.id, c2.id],
                            expected_value=f"{c1.claimed_amount:.2f}",
                            observed_value=f"{c2.claimed_amount:.2f}",
                        ))
        return discrepancies

    @classmethod
    def _normalize_ref(cls, ref: str) -> str:
        """Strip formatting, prefixes (UTR, RRN, REF, TXN), and whitespace."""
        cleaned = re.sub(r"^[\s]*(?:UTR|RRN|REF|TXN|INV)[:\s\-_]*", "", str(ref), flags=re.IGNORECASE)
        return re.sub(r"[\s\-_/]", "", cleaned).upper()

    @classmethod
    def _parse_date(cls, date_str: str) -> Optional[datetime]:
        """Parses various date formats."""
        cleaned = date_str.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except Exception:
            return None
