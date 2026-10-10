"""Report Builder for VERITY Financial Truth Reports."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.reconciliation import ReconciliationStatus
from backend.domain.transaction import Transaction
from backend.reconciliation.result import ReconciliationResult
from backend.reporting.explainability import ExplainabilityEngine
from backend.reporting.models import (
    ClaimSummaryItem,
    ContradictionSummaryItem,
    EntitySummary,
    EvidenceSummaryItem,
    FinancialSummary,
    FinancialTruthReport,
    MatchingSummary,
    ProvenanceReferences,
    ReconciliationSummary,
    ReportStatus,
    TransactionSummaryItem,
)
from backend.transaction_matching.result import MatchRelationship


class FinancialTruthReportBuilder:
    """Transforms Day 8 reconciliation outputs and domain artifacts into an explainable Financial Truth Report."""

    @classmethod
    def build_report(
        cls,
        reconciliation_result: ReconciliationResult,
        claims: Optional[List[Claim]] = None,
        transactions: Optional[List[Transaction]] = None,
        evidence: Optional[List[Evidence]] = None,
        entities: Optional[List[Entity]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        case_id: Optional[str] = None,
    ) -> FinancialTruthReport:
        """Assembles a structured FinancialTruthReport from verified domain outputs."""
        clms = claims or []
        txns = transactions or []
        ev_list = evidence or []
        ents = entities or []
        match_rels = match_relationships or []
        dedup_grps = deduplication_groups or []
        discs = discrepancies or []

        cid = case_id or reconciliation_result.event_id or f"CASE-{uuid.uuid4().hex[:6].upper()}"
        report_id = f"REP-{uuid.uuid4().hex[:8].upper()}"

        # 1. Resolve Entity Details
        target_entity: Optional[Entity] = None
        if reconciliation_result.entity_id:
            target_entity = next((e for e in ents if e.id == reconciliation_result.entity_id), None)
        if not target_entity and ents:
            target_entity = ents[0]

        ent_name = target_entity.canonical_name if target_entity else (
            clms[0].counterparty_hint if clms and clms[0].counterparty_hint else "Unknown Counterparty"
        )
        ent_summary = EntitySummary(
            entity_id=target_entity.id if target_entity else reconciliation_result.entity_id,
            canonical_name=ent_name,
            entity_type=target_entity.entity_type.value if target_entity and hasattr(target_entity.entity_type, "value") else None,
            gstin=target_entity.gstin if target_entity else None,
            pan=target_entity.pan if target_entity else None,
            upi_id=target_entity.upi_ids[0] if target_entity and target_entity.upi_ids else None,
            phone=target_entity.phone_numbers[0] if target_entity and target_entity.phone_numbers else None,
            resolved_via=target_entity.metadata.get("resolved_via") if target_entity else None,
        )

        # 2. Financial Summary
        fin_summary = FinancialSummary(
            claimed_amount=reconciliation_result.expected_amount,
            matched_amount=reconciliation_result.matched_amount,
            outstanding_amount=reconciliation_result.outstanding_amount,
            currency=reconciliation_result.currency,
            claim_count=len(clms),
            transaction_count=len(txns),
            evidence_count=len(ev_list),
        )

        # 3. Evidence Summary Items
        ev_summaries: List[EvidenceSummaryItem] = []
        for e in ev_list:
            ev_summaries.append(EvidenceSummaryItem(
                evidence_id=e.id,
                modality=e.modality.value if hasattr(e.modality, "value") else str(e.modality),
                source_name=e.source_name,
                source_type=e.source_type.value if hasattr(e.source_type, "value") else str(e.source_type),
                sha256_hash=e.content_hash,
                summary=f"{e.modality.value if hasattr(e.modality, 'value') else e.modality} via {e.source_name or (e.source_type.value if hasattr(e.source_type, 'value') else e.source_type)}",
            ))

        # 4. Claims Summary Items
        clm_summaries: List[ClaimSummaryItem] = []
        for c in clms:
            clm_summaries.append(ClaimSummaryItem(
                claim_id=c.id,
                evidence_id=c.evidence_id,
                claim_type=c.claim_type.value,
                claimed_amount=c.claimed_amount,
                claimed_date=c.claimed_date,
                counterparty_hint=c.counterparty_hint,
                reference_id_hint=c.reference_id_hint,
                confidence=c.confidence,
            ))

        # 5. Transactions Summary Items
        txn_summaries: List[TransactionSummaryItem] = []
        for t in txns:
            txn_summaries.append(TransactionSummaryItem(
                transaction_id=t.id,
                amount=t.amount,
                direction=t.direction.value,
                timestamp=t.timestamp.isoformat() if t.timestamp else None,
                bank_reference=t.bank_reference,
                payment_method=t.payment_method.value if t.payment_method else None,
                counterparty_entity_id=t.origin_entity_id or t.destination_entity_id,
            ))

        # 6. Matching Summary
        m_summary: Optional[MatchingSummary] = None
        target_rel = match_rels[0] if match_rels else None
        if target_rel:
            m_summary = MatchingSummary(
                match_relationship_id=target_rel.id,
                topology=target_rel.relationship_type.value,
                status=target_rel.status.value,
                score=target_rel.score,
                matched_signals=target_rel.matched_signals,
                conflicting_signals=target_rel.conflicting_signals,
                explanation=target_rel.explanation,
            )

        # 7. Contradictions Summary Items
        disc_summaries: List[ContradictionSummaryItem] = []
        for d in discs:
            disc_summaries.append(ContradictionSummaryItem(
                discrepancy_id=d.id,
                discrepancy_type=d.discrepancy_type.value,
                severity=d.severity.value,
                message=d.message,
                expected_value=d.expected_value,
                observed_value=d.observed_value,
                involved_evidence_ids=d.involved_evidence_ids,
            ))

        # 8. Reconciliation Summary
        recon_summary = ReconciliationSummary(
            reconciliation_id=reconciliation_result.reconciliation_id,
            status=reconciliation_result.status.value,
            expected_amount=reconciliation_result.expected_amount,
            matched_amount=reconciliation_result.matched_amount,
            outstanding_amount=reconciliation_result.outstanding_amount,
            confidence_score=reconciliation_result.confidence_score,
            reason_codes=reconciliation_result.reason_codes,
        )

        # 9. Natural Language Explanations & Factor Breakdown
        title = ExplainabilityEngine.generate_title(
            status=reconciliation_result.status,
            expected_amount=reconciliation_result.expected_amount,
            matched_amount=reconciliation_result.matched_amount,
            entity_name=ent_name,
        )
        summary_text = ExplainabilityEngine.generate_executive_summary(
            status=reconciliation_result.status,
            expected_amount=reconciliation_result.expected_amount,
            matched_amount=reconciliation_result.matched_amount,
            outstanding_amount=reconciliation_result.outstanding_amount,
            entity_name=ent_name,
            discrepancies=discs,
        )
        detailed_explanation = ExplainabilityEngine.generate_detailed_explanation(
            reconciliation_result=reconciliation_result,
            claims=clms,
            transactions=txns,
            evidence=ev_list,
            discrepancies=discs,
            entity=target_entity,
            match_relationship=target_rel,
        )
        confidence_factors = ExplainabilityEngine.generate_confidence_breakdown(
            reconciliation_result=reconciliation_result,
            evidence=ev_list,
            discrepancies=discs,
            match_relationship=target_rel,
        )
        unresolved_items = ExplainabilityEngine.generate_unresolved_items(
            reconciliation_result=reconciliation_result,
            discrepancies=discs,
        )
        recommended_actions = ExplainabilityEngine.generate_recommended_actions(
            status=reconciliation_result.status,
            outstanding_amount=reconciliation_result.outstanding_amount,
            discrepancies=discs,
        )

        # 10. Provenance References
        prov_refs = ProvenanceReferences(
            evidence_ids=list(set(reconciliation_result.evidence_ids + [e.id for e in ev_list])),
            claim_ids=list(set(reconciliation_result.claim_ids + [c.id for c in clms])),
            transaction_ids=list(set(reconciliation_result.transaction_ids + [t.id for t in txns])),
            entity_ids=[target_entity.id] if target_entity else ([reconciliation_result.entity_id] if reconciliation_result.entity_id else []),
            match_relationship_ids=[m.id for m in match_rels],
            deduplication_group_ids=[g.group_id for g in dedup_grps],
            discrepancy_ids=[d.id for d in discs],
            reconciliation_id=reconciliation_result.reconciliation_id,
        )

        # Map ReportStatus
        rep_status = ReportStatus(reconciliation_result.status.value)

        return FinancialTruthReport(
            report_id=report_id,
            case_id=cid,
            status=rep_status,
            confidence_score=reconciliation_result.confidence_score,
            title=title,
            summary=summary_text,
            entity_summary=ent_summary,
            financial_summary=fin_summary,
            evidence_summary=ev_summaries,
            claims_summary=clm_summaries,
            transaction_summary=txn_summaries,
            matching_summary=m_summary,
            contradiction_summary=disc_summaries,
            reconciliation_summary=recon_summary,
            confidence_breakdown=confidence_factors,
            explanation=detailed_explanation,
            unresolved_items=unresolved_items,
            recommended_actions=recommended_actions,
            provenance=prov_refs,
            metadata={"buildathon_track": "AI Finance Controller", "day": "Day 9"},
        )
