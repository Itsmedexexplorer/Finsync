"""Unit tests for PairwiseSignalEvaluator in Transaction Matching."""

from datetime import datetime, timezone
import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import PaymentMethod, Transaction, TransactionDirection
from backend.transaction_matching.signals import PairwiseSignalEvaluator


def test_signals_exact_reference_match() -> None:
    claim = Claim(
        id="CLM-01",
        evidence_id="EVID-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=25000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-01",
        amount=25000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
    )

    score, ms, cs, exp = PairwiseSignalEvaluator.evaluate_pair(claim, txn)
    assert score >= 0.98
    assert "EXACT_REFERENCE" in ms
    assert "EXACT_AMOUNT_MATCH" in ms
    assert len(cs) == 0


def test_signals_reference_inside_narration() -> None:
    claim = Claim(
        id="CLM-02",
        evidence_id="EVID-02",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=15000.0,
        reference_id_hint="INV-2026-088",
    )
    txn = Transaction(
        id="TXN-02",
        amount=15000.0,
        direction=TransactionDirection.CREDIT,
        narration="NEFT/PAYMENT FOR INV-2026-088/HDFC",
    )

    score, ms, cs, exp = PairwiseSignalEvaluator.evaluate_pair(claim, txn)
    assert score >= 0.98
    assert "EXACT_REFERENCE_IN_NARRATION" in ms


def test_signals_entity_and_date_proximity() -> None:
    claim = Claim(
        id="CLM-03",
        evidence_id="EVID-03",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=30000.0,
        claimed_date="2026-08-10",
    )
    txn = Transaction(
        id="TXN-03",
        amount=30000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-001",
        timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc),
    )

    score, ms, cs, exp = PairwiseSignalEvaluator.evaluate_pair(
        claim=claim,
        transaction=txn,
        claim_entity_id="ENT-001",
    )
    assert score >= 0.95
    assert "EXACT_ENTITY_MATCH" in ms
    assert "DATE_PROXIMITY" in ms
    assert "EXACT_AMOUNT_MATCH" in ms


def test_signals_detects_conflicting_entity() -> None:
    claim = Claim(
        id="CLM-04",
        evidence_id="EVID-04",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=20000.0,
    )
    txn = Transaction(
        id="TXN-04",
        amount=20000.0,
        direction=TransactionDirection.CREDIT,
        origin_entity_id="ENT-002",
    )

    score, ms, cs, exp = PairwiseSignalEvaluator.evaluate_pair(
        claim=claim,
        transaction=txn,
        claim_entity_id="ENT-001",  # Different entity!
    )
    assert "CONFLICTING_ENTITY" in cs
    assert score < 0.60
