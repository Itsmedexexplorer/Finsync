"""Unit tests for Unverifiable Claims in Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.reconciliation import ReconciliationStatus
from backend.reconciliation.engine import ReconciliationEngine


@pytest.fixture
def engine() -> ReconciliationEngine:
    return ReconciliationEngine()


def test_claim_without_amount_and_no_ledger_is_unverifiable(engine: ReconciliationEngine) -> None:
    """'I sent the money' without amount and no ledger transaction -> UNVERIFIABLE."""
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.PAYMENT_SENT,
        claimed_amount=None,
    )

    result = engine.reconcile(claims=[claim], transactions=[])
    assert len(result.results) == 1
    res = result.results[0]
    assert res.status == ReconciliationStatus.UNVERIFIABLE
    assert res.matched_amount == 0.0
