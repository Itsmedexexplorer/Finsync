"""Unit tests verifying Provenance Integrity in Reconciliation."""

import pytest
from backend.domain.claim import Claim, ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.provenance import ProvenanceNodeType
from backend.domain.transaction import Transaction, TransactionDirection
from backend.provenance.tracker import ProvenanceTracker
from backend.reconciliation.engine import ReconciliationEngine


def test_reconciliation_provenance_dag_traceability() -> None:
    ev = Evidence(id="E-PROV-01", modality=EvidenceModality.INVOICE, source_type=EvidenceSourceType.ZOHO_INVOICE, source_name="inv.pdf", raw_payload="Invoice 10k")
    clm = Claim(id="C-PROV-01", evidence_id="E-PROV-01", claim_type=ClaimType.INVOICE_ISSUED, claimed_amount=10000.0)
    txn = Transaction(id="T-PROV-01", amount=10000.0, direction=TransactionDirection.CREDIT, evidence_ids=["E-PROV-01"])

    tracker = ProvenanceTracker()
    engine = ReconciliationEngine(provenance_tracker=tracker)

    batch_result = engine.reconcile(
        claims=[clm],
        transactions=[txn],
        evidence_items=[ev],
    )

    assert len(batch_result.results) == 1
    res = batch_result.results[0]

    # Verify that reconciliation is tracked in provenance DAG
    rec_nodes = [n for n in tracker.audit_trail.nodes.values() if n.node_type == ProvenanceNodeType.RECONCILIATION]
    assert len(rec_nodes) == 1
    assert rec_nodes[0].source_reference == res.reconciliation_id
