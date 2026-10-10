"""Pytest fixtures for VERITY test suites."""

from __future__ import annotations

import os

# The API test-suite exercises the demo scenarios, which are disabled by default.
os.environ.setdefault("VERITY_ENABLE_DEMO", "true")

# Never write test data into the developer's real local database.
import tempfile as _tempfile

_TEST_DATA_DIR = _tempfile.mkdtemp(prefix="verity_tests_")
os.environ["VERITY_DATABASE_URL"] = f"sqlite:///{_TEST_DATA_DIR}/verity.db"
os.environ["VERITY_WORKSPACE_DIR"] = f"{_TEST_DATA_DIR}/workspaces"
for _var in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.pop(_var, None)

import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.claim import Claim, ClaimType, ClaimStatus
from backend.domain.entity import Entity, EntityType
from backend.domain.transaction import Transaction, TransactionDirection, PaymentMethod
from backend.domain.discrepancy import Discrepancy, DiscrepancyType, DiscrepancySeverity
from data.benchmark.loader import BenchmarkCase, load_benchmark_cases


@pytest.fixture
def sample_evidence() -> Evidence:
    """Fixture for standard bank statement line evidence."""
    return Evidence(
        id="EVID-TEST-001",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="HDFC_Aug2026.csv",
        raw_payload="15/08/2026,UPI/408219381920/PAYTO/ROHIT,35000.00,0.00,120000.00",
    )


@pytest.fixture
def sample_claim() -> Claim:
    """Fixture for standard extracted invoice claim."""
    return Claim(
        id="CLM-TEST-001",
        evidence_id="EVID-TEST-001",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=35000.0,
        claimed_date="2026-08-15",
        counterparty_hint="Rohit Verma",
        reference_id_hint="INV-2026-001",
    )


@pytest.fixture
def sample_entity() -> Entity:
    """Fixture for Indian freelancer entity with multiple aliases and UPI handles."""
    return Entity(
        id="ENT-TEST-001",
        canonical_name="Rohit Verma",
        entity_type=EntityType.FREELANCER,
        pan="ABCDE1234F",
        upi_ids=["rohit@okhdfcbank", "9876543210@paytm"],
        phone_numbers=["+919876543210"],
        aliases=["Rohit", "M/s Rohit Tech", "ROHIT V"],
    )


@pytest.fixture
def sample_transaction() -> Transaction:
    """Fixture for standard verified credit transaction."""
    return Transaction(
        id="TXN-TEST-001",
        amount=35000.0,
        direction=TransactionDirection.CREDIT,
        payment_method=PaymentMethod.UPI,
        bank_reference="408219381920",
        narration="UPI/408219381920/PAYTO/ROHIT",
        evidence_ids=["EVID-TEST-001"],
    )


@pytest.fixture(scope="session")
def benchmark_cases() -> List[BenchmarkCase]:
    """Fixture loading all 96 ground-truth benchmark cases once per test session."""
    return load_benchmark_cases()


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Each test starts with fresh rate-limit counters."""
    from backend.api.rate_limit import limiter

    limiter.reset()
    yield
