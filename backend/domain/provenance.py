"""Domain model for immutable evidence provenance and financial audit trails.

Enables full trace back from any financial conclusion or discrepancy to the raw evidence
artifacts and intermediate transformation steps.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class ProvenanceNodeType(str, Enum):
    """The type of domain node in the provenance graph."""
    EVIDENCE = "EVIDENCE"
    CLAIM = "CLAIM"
    ENTITY = "ENTITY"
    TRANSACTION = "TRANSACTION"
    DISCREPANCY = "DISCREPANCY"
    RECONCILIATION = "RECONCILIATION"


class ProvenanceNode(BaseModel):
    """An individual verifiable step or artifact in the financial reconciliation graph."""
    node_id: str = Field(..., description="Unique identifier for the provenance node")
    node_type: ProvenanceNodeType = Field(..., description="Category of the domain artifact")
    source_reference: str = Field(..., description="Target object ID, e.g. 'EVID-001' or 'CLM-002'")
    content_hash: str = Field(..., description="Cryptographic SHA-256 hash of the node's state")
    parent_node_ids: List[str] = Field(
        default_factory=list,
        description="Direct upstream nodes from which this node was derived"
    )
    transformation_rule: Optional[str] = Field(
        default=None,
        description="Rule, extraction logic, or matching algorithm that created this derivation"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this provenance step was recorded"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional diagnostic and execution metadata"
    )


class AuditTrail(BaseModel):
    """A Directed Acyclic Graph (DAG) of ProvenanceNodes maintaining end-to-end audit lineage."""
    nodes: Dict[str, ProvenanceNode] = Field(
        default_factory=dict,
        description="Map of node_id -> ProvenanceNode"
    )

    def record_node(
        self,
        node_id: str,
        node_type: ProvenanceNodeType,
        source_reference: str,
        content_payload: str,
        parent_node_ids: Optional[List[str]] = None,
        transformation_rule: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProvenanceNode:
        """Create and register a new provenance node with SHA-256 fingerprinting."""
        content_hash = hashlib.sha256(content_payload.encode("utf-8")).hexdigest()
        parents = parent_node_ids or []
        node = ProvenanceNode(
            node_id=node_id,
            node_type=node_type,
            source_reference=source_reference,
            content_hash=content_hash,
            parent_node_ids=parents,
            transformation_rule=transformation_rule,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        return node

    def get_ancestors(self, node_id: str) -> List[ProvenanceNode]:
        """Traverse the DAG upwards to retrieve all upstream ancestor nodes."""
        visited: Set[str] = set()
        ancestors: List[ProvenanceNode] = []
        stack: List[str] = list(self.nodes.get(node_id, ProvenanceNode(
            node_id="",
            node_type=ProvenanceNodeType.EVIDENCE,
            source_reference="",
            content_hash=""
        )).parent_node_ids)

        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)
            if current_id in self.nodes:
                node = self.nodes[current_id]
                ancestors.append(node)
                stack.extend(node.parent_node_ids)

        return ancestors

    def get_root_evidence_ids(self, node_id: str) -> List[str]:
        """Find all root EVIDENCE source_references that contributed to a given node."""
        ancestors = self.get_ancestors(node_id)
        if node_id in self.nodes and self.nodes[node_id].node_type == ProvenanceNodeType.EVIDENCE:
            return [self.nodes[node_id].source_reference]
        return [
            node.source_reference
            for node in ancestors
            if node.node_type == ProvenanceNodeType.EVIDENCE
        ]
