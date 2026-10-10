"""Unit tests for EventFingerprint and DeduplicationSignalEvaluator."""

import pytest
from backend.deduplication.fingerprint import EventFingerprint
from backend.deduplication.signals import DeduplicationSignalEvaluator


def test_event_fingerprint_reference_normalization() -> None:
    assert EventFingerprint.get_reference_key("408219381920") == "REF:408219381920"
    assert EventFingerprint.get_reference_key("UTR-408-219-381920") == "REF:408219381920"
    assert EventFingerprint.get_reference_key("RRN: 408219381920") == "REF:408219381920"
    assert EventFingerprint.get_reference_key(None) is None


def test_signals_detects_conflicting_amounts() -> None:
    """When same UTR reference is cited, but one source says 20k and other says 50k -> CONFLICTING_AMOUNT."""
    score, ms, cs, exp = DeduplicationSignalEvaluator.evaluate_correlation(
        ref_a="408219381920",
        ref_b="408219381920",
        amt_a=20000.0,
        amt_b=50000.0,
        ent_a="ENT-001",
        ent_b="ENT-001",
        date_a="2026-08-15",
        date_b="2026-08-15",
    )
    assert "CONFLICTING_AMOUNT" in cs
    assert score < 0.70
    assert "conflicting amounts" in exp


def test_signals_detects_conflicting_entities() -> None:
    """When amounts/dates align but entities conflict -> CONFLICTING_ENTITY."""
    score, ms, cs, exp = DeduplicationSignalEvaluator.evaluate_correlation(
        ref_a=None,
        ref_b=None,
        amt_a=20000.0,
        amt_b=20000.0,
        ent_a="ENT-RAHUL",
        ent_b="ENT-ROHIT",
        date_a="2026-08-15",
        date_b="2026-08-15",
    )
    assert "CONFLICTING_ENTITY" in cs
    assert score < 0.60
