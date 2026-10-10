"""Serialization helpers converting domain results into API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.api.models import (
    CaseResponse,
    FinancialSummaryResponse,
    ProvenanceGraphResponse,
    ProvenanceNodeResponse,
    StageRecordResponse,
)
from backend.case_processing.result import CaseProcessingResult
from backend.provenance.tracker import ProvenanceTracker


def serialize_case_result(
    result: CaseProcessingResult,
    provenance_tracker: Optional[ProvenanceTracker] = None,
) -> CaseResponse:
    """Serializes a canonical CaseProcessingResult into the API response model."""
    status_str = result.status.upper()
    requires_review = status_str in (
        "CONTRADICTED",
        "AMBIGUOUS",
        "UNMATCHED",
        "UNVERIFIABLE",
        "PARTIALLY_SETTLED",
        "PARTIAL",
    )

    fin_sum = result.financial_summary
    financial_summary_resp = FinancialSummaryResponse(
        claimed_amount=fin_sum.get("claimed_amount"),
        matched_amount=fin_sum.get("matched_amount", 0.0),
        outstanding_amount=fin_sum.get("outstanding_amount", 0.0),
        total_reconciled_batch=fin_sum.get("total_reconciled_batch", 0.0),
        total_outstanding_batch=fin_sum.get("total_outstanding_batch", 0.0),
        evidence_count=fin_sum.get("evidence_count", 0),
        claims_count=fin_sum.get("claims_count", 0),
        transactions_count=fin_sum.get("transactions_count", 0),
        discrepancies_count=fin_sum.get("discrepancies_count", 0),
    )

    stage_records_resp: List[StageRecordResponse] = []
    for rec in result.stage_records:
        stage_records_resp.append(StageRecordResponse(
            stage=rec.stage.value if hasattr(rec.stage, "value") else str(rec.stage),
            status=rec.status,
            duration_ms=rec.duration_ms,
            items_in=rec.items_in,
            items_out=rec.items_out,
            notes=rec.notes,
        ))

    truth_report_dict = result.report.model_dump() if result.report else None
    
    # Provenance summary
    prov_dict = None
    if result.report and result.report.provenance:
        prov_dict = result.report.provenance.model_dump()

    return CaseResponse(
        case_id=result.case_id,
        status=result.status,
        confidence=round(result.confidence_score, 4),
        requires_review=requires_review,
        financial_summary=financial_summary_resp,
        truth_report=truth_report_dict,
        stage_execution=stage_records_resp,
        provenance=prov_dict,
        total_execution_time_ms=result.total_execution_time_ms,
        warnings=result.warnings,
        errors=result.errors,
        text_report=result.to_text_report(),
    )


def serialize_provenance_graph(
    case_id: str,
    tracker: ProvenanceTracker,
) -> ProvenanceGraphResponse:
    """Builds a structured provenance DAG response for visualization."""
    nodes_resp: List[ProvenanceNodeResponse] = []
    root_ids: List[str] = []

    for nid, node in tracker.audit_trail.nodes.items():
        node_type_str = node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type)
        if node_type_str == "EVIDENCE":
            root_ids.append(nid)

        nodes_resp.append(ProvenanceNodeResponse(
            node_id=nid,
            node_type=node_type_str,
            label=f"{node_type_str}: {nid}",
            content_hash=node.content_hash,
            parent_ids=list(node.parent_node_ids),
            timestamp=node.timestamp.isoformat() if hasattr(node.timestamp, "isoformat") else str(node.timestamp),
        ))

    return ProvenanceGraphResponse(
        case_id=case_id,
        total_nodes=len(nodes_resp),
        nodes=nodes_resp,
        root_evidence_ids=root_ids,
    )
