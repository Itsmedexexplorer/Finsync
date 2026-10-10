"""Unit tests for the VERITY Provenance and Lineage Tracker."""

import pytest
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.claim import Claim, ClaimType
from backend.domain.transaction import Transaction, TransactionDirection, PaymentMethod
from backend.domain.reconciliation import ReconciliationRecord, ReconciliationStatus, MatchType
from backend.domain.provenance import ProvenanceNodeType
from backend.provenance.tracker import ProvenanceTracker


def test_provenance_tracker_dag_lineage() -> None:
    tracker = ProvenanceTracker()

    # 1. Raw Ingested Evidence
    evidence = Evidence(
        id="EVID-101",
        modality=EvidenceModality.INVOICE,
        source_type=EvidenceSourceType.ZOHO_INVOICE,
        source_name="INV-101.pdf",
        raw_payload="INVOICE #INV-101 | Total Due: Rs. 45,000.00",
    )
    evid_node = tracker.track_evidence(evidence)
    assert evid_node.node_type == ProvenanceNodeType.EVIDENCE
    assert evid_node.source_reference == "EVID-101"

    # 2. Extracted Claim
    claim = Claim(
        id="CLM-101",
        evidence_id=evidence.id,
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=45000.0,
        raw_text_snippet="Total Due: Rs. 45,000.00",
    )
    claim_node = tracker.track_claim(claim)
    assert claim_node.node_type == ProvenanceNodeType.CLAIM
    assert evid_node.node_id in claim_node.parent_node_ids

    # 3. Bank Statement Evidence & Transaction
    bank_evid = Evidence(
        id="EVID-102",
        modality=EvidenceModality.BANK_STATEMENT,
        source_type=EvidenceSourceType.BANK_CSV,
        source_name="hdfc.csv",
        raw_payload="12/08/2026,UPI/408219381920/INV-101,45000.00,0.00,500000.00",
    )
    tracker.track_evidence(bank_evid)

    txn = Transaction(
        id="TXN-101",
        amount=45000.0,
        direction=TransactionDirection.CREDIT,
        payment_method=PaymentMethod.UPI,
        bank_reference="408219381920",
        evidence_ids=[bank_evid.id],
    )
    txn_node = tracker.track_transaction(txn)
    assert f"prov-evid-{bank_evid.id}" in txn_node.parent_node_ids

    # 4. Reconciliation Record
    rec = ReconciliationRecord(
        id="REC-101",
        status=ReconciliationStatus.CONFIRMED,
        match_type=MatchType.EXACT_1_TO_1,
        expected_amount=45000.0,
        reconciled_amount=45000.0,
        outstanding_amount=0.0,
        claim_ids=[claim.id],
        transaction_ids=[txn.id],
        explanation_summary="Exact match verified.",
    )
    rec_node = tracker.track_reconciliation(rec)

    # Verify DAG traversal
    ancestors = tracker.audit_trail.get_ancestors(rec_node.node_id)
    ancestor_refs = {a.source_reference for a in ancestors}
    assert "CLM-101" in ancestor_refs
    assert "TXN-101" in ancestor_refs

    # Verify Root Evidence Lineage
    root_evid_ids = tracker.audit_trail.get_root_evidence_ids(rec_node.node_id)
    assert "EVID-101" in root_evid_ids
    assert "EVID-102" in root_evid_ids
