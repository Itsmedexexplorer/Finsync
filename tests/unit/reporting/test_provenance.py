"""Unit tests verifying Provenance References in Financial Truth Reports."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.discrepancy import Discrepancy, DiscrepancySeverity, DiscrepancyType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction, TransactionDirection
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.service import ReportingService


def test_provenance_references_populated() -> None:
    ev = Evidence(id="E-PROV-1", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="i.pdf", raw_payload="1")
    clm = Claim(id="C-PROV-1", evidence_id="E-PROV-1", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=50000.0)
    txn = Transaction(id="T-PROV-1", amount=50000.0, direction=TransactionDirection.CREDIT, bank_reference="408219381920")
    disc = Discrepancy(id="D-PROV-1", discrepancy_type=DiscrepancyType.PAYMENT_RAIL_MISMATCH, severity=DiscrepancySeverity.INFO, message="Rail info")

    recon_res = ReconciliationResult(
        reconciliation_id="REC-PROV-01",
        status=ReconciliationStatus.CONFIRMED,
        expected_amount=50000.0,
        matched_amount=50000.0,
        outstanding_amount=0.0,
        confidence_score=1.0,
        explanation="Confirmed",
        claim_ids=["C-PROV-1"],
        transaction_ids=["T-PROV-1"],
        evidence_ids=["E-PROV-1"],
    )

    service = ReportingService()
    report = service.build_report(
        reconciliation_result=recon_res,
        claims=[clm],
        transactions=[txn],
        evidence=[ev],
        discrepancies=[disc],
    )

    assert "E-PROV-1" in report.provenance.evidence_ids
    assert "C-PROV-1" in report.provenance.claim_ids
    assert "T-PROV-1" in report.provenance.transaction_ids
    assert "D-PROV-1" in report.provenance.discrepancy_ids
    assert report.provenance.reconciliation_id == "REC-PROV-01"
