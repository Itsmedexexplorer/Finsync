"""Provenance tracking engine for maintaining cryptographic audit lineage."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional
from backend.domain.evidence import Evidence
from backend.domain.claim import Claim
from backend.domain.entity import Entity
from backend.domain.transaction import Transaction
from backend.domain.discrepancy import Discrepancy
from backend.domain.reconciliation import ReconciliationRecord
from backend.domain.provenance import AuditTrail, ProvenanceNode, ProvenanceNodeType


class ProvenanceTracker:
    """Manages the lifecycle of the reconciliation provenance DAG."""

    def __init__(self, audit_trail: Optional[AuditTrail] = None) -> None:
        self.audit_trail = audit_trail or AuditTrail()

    def track_evidence(self, evidence: Evidence) -> ProvenanceNode:
        """Register raw evidence as a root provenance node."""
        node_id = f"prov-evid-{evidence.id}"
        payload = f"{evidence.id}|{evidence.modality.value}|{evidence.raw_payload}"
        return self.audit_trail.record_node(
            node_id=node_id,
            node_type=ProvenanceNodeType.EVIDENCE,
            source_reference=evidence.id,
            content_payload=payload,
            parent_node_ids=[],
            transformation_rule="RAW_INGESTION",
            metadata={"source_name": evidence.source_name, "source_type": evidence.source_type.value},
        )

    def track_claim(self, claim: Claim, rule: str = "CLAIM_EXTRACTION") -> ProvenanceNode:
        """Register an extracted claim linked to its parent evidence provenance node."""
        node_id = f"prov-claim-{claim.id}"
        parent_node_id = f"prov-evid-{claim.evidence_id}"
        payload = f"{claim.id}|{claim.claim_type.value}|{claim.claimed_amount}|{claim.reference_id_hint or ''}"
        return self.audit_trail.record_node(
            node_id=node_id,
            node_type=ProvenanceNodeType.CLAIM,
            source_reference=claim.id,
            content_payload=payload,
            parent_node_ids=[parent_node_id],
            transformation_rule=rule,
            metadata={"confidence": claim.confidence, "status": claim.status.value},
        )

    def track_transaction(
        self,
        transaction: Transaction,
        rule: str = "LEDGER_INGESTION",
    ) -> ProvenanceNode:
        """Register a verified transaction linked to its supporting evidence provenance nodes."""
        node_id = f"prov-txn-{transaction.id}"
        parents = [f"prov-evid-{evid_id}" for evid_id in transaction.evidence_ids]
        payload = f"{transaction.id}|{transaction.amount}|{transaction.direction.value}|{transaction.bank_reference or ''}"
        return self.audit_trail.record_node(
            node_id=node_id,
            node_type=ProvenanceNodeType.TRANSACTION,
            source_reference=transaction.id,
            content_payload=payload,
            parent_node_ids=parents,
            transformation_rule=rule,
            metadata={"payment_method": transaction.payment_method.value},
        )

    def track_discrepancy(
        self,
        discrepancy: Discrepancy,
        rule: str = "DISCREPANCY_DETECTION",
    ) -> ProvenanceNode:
        """Register a detected discrepancy linked to involved claims, transactions, and evidence."""
        node_id = f"prov-disc-{discrepancy.id}"
        parents: List[str] = []
        parents.extend([f"prov-evid-{eid}" for eid in discrepancy.involved_evidence_ids])
        parents.extend([f"prov-claim-{cid}" for cid in discrepancy.involved_claim_ids])
        parents.extend([f"prov-txn-{tid}" for tid in discrepancy.involved_transaction_ids])
        
        payload = f"{discrepancy.id}|{discrepancy.discrepancy_type.value}|{discrepancy.message}"
        return self.audit_trail.record_node(
            node_id=node_id,
            node_type=ProvenanceNodeType.DISCREPANCY,
            source_reference=discrepancy.id,
            content_payload=payload,
            parent_node_ids=parents,
            transformation_rule=rule,
            metadata={"severity": discrepancy.severity.value},
        )

    def track_reconciliation(
        self,
        reconciliation: ReconciliationRecord,
        rule: str = "SYNTHESIS_RECONCILIATION_ENGINE",
    ) -> ProvenanceNode:
        """Register the final reconciliation conclusion linked to all evaluated claims, txns, and discrepancies."""
        node_id = f"prov-rec-{reconciliation.id}"
        parents: List[str] = []
        parents.extend([f"prov-claim-{cid}" for cid in reconciliation.claim_ids])
        parents.extend([f"prov-txn-{tid}" for tid in reconciliation.transaction_ids])
        parents.extend([f"prov-disc-{d.id}" for d in reconciliation.discrepancies])
        
        payload = f"{reconciliation.id}|{reconciliation.status.value}|{reconciliation.reconciled_amount}"
        return self.audit_trail.record_node(
            node_id=node_id,
            node_type=ProvenanceNodeType.RECONCILIATION,
            source_reference=reconciliation.id,
            content_payload=payload,
            parent_node_ids=parents,
            transformation_rule=rule,
            metadata={
                "status": reconciliation.status.value,
                "confidence": reconciliation.confidence_score,
            },
        )
