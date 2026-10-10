"""Unit tests verifying provenance linkage of detected contradictions."""

import pytest
from backend.contradiction_detection.detector import ContradictionDetector
from backend.domain.claim import Claim, ClaimType
from backend.domain.provenance import AuditTrail, ProvenanceNodeType
from backend.domain.transaction import Transaction, TransactionDirection


def test_contradiction_provenance_traceability() -> None:
    claim = Claim(
        id="CLM-PROV-01",
        evidence_id="EVID-ORIG-01",
        claim_type=ClaimType.INVOICE_ISSUED,
        claimed_amount=50000.0,
        reference_id_hint="408219381920",
    )
    txn = Transaction(
        id="TXN-PROV-01",
        amount=35000.0,
        direction=TransactionDirection.CREDIT,
        bank_reference="408219381920",
        evidence_ids=["EVID-ORIG-02"],
    )

    detector = ContradictionDetector()
    result = detector.detect(claims=[claim], transactions=[txn])
    assert len(result.discrepancies) == 1
    disc = result.discrepancies[0]

    # Verify that discrepancy records root evidence references
    assert "EVID-ORIG-01" in disc.involved_evidence_ids
    assert "EVID-ORIG-02" in disc.involved_evidence_ids
    assert "CLM-PROV-01" in disc.involved_claim_ids
    assert "TXN-PROV-01" in disc.involved_transaction_ids

    # Record into AuditTrail DAG
    audit_trail = AuditTrail()
    audit_trail.record_node(
        node_id="NODE-EV-01",
        node_type=ProvenanceNodeType.EVIDENCE,
        source_reference="EVID-ORIG-01",
        content_payload="RAW_INVOICE_EVIDENCE",
    )
    audit_trail.record_node(
        node_id="NODE-DISC-01",
        node_type=ProvenanceNodeType.DISCREPANCY,
        source_reference=disc.id,
        content_payload=disc.model_dump_json(),
        parent_node_ids=["NODE-EV-01"],
        transformation_rule="RULE_AMOUNT_001",
    )

    roots = audit_trail.get_root_evidence_ids("NODE-DISC-01")
    assert roots == ["EVID-ORIG-01"]
