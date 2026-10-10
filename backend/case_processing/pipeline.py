"""Deterministic Finance Controller Pipeline for VERITY.

Coordinates the 8 sequential stages:
1. Ingestion & Normalization
2. Claims & Transaction Extraction
3. Deterministic Entity Resolution
4. Transaction Matching
5. Cross-Modal Evidence Deduplication
6. Deterministic Contradiction Detection
7. Financial Reconciliation
8. Explainable Financial Truth Reporting
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from backend.case_processing.context import CaseProcessingContext
from backend.case_processing.models import CaseInput, PipelineStage, StageExecutionRecord
from backend.case_processing.result import CaseProcessingResult
from backend.contradiction_detection.service import ContradictionDetectionService
from backend.deduplication.service import DeduplicationService
from backend.domain.claim import Claim
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction
from backend.entity_resolution.service import EntityResolutionService
from backend.extraction.service import ExtractionService
from backend.ingestion.service import IngestionService
from backend.provenance.tracker import ProvenanceTracker
from backend.reconciliation.service import ReconciliationService
from backend.reporting.service import ReportingService
from backend.transaction_matching.service import TransactionMatchingService


class FinanceControllerPipeline:
    """The central deterministic orchestrator for end-to-end financial truth reconstruction."""

    def __init__(
        self,
        ingestion_service: Optional[IngestionService] = None,
        extraction_service: Optional[ExtractionService] = None,
        entity_service: Optional[EntityResolutionService] = None,
        matching_service: Optional[TransactionMatchingService] = None,
        deduplication_service: Optional[DeduplicationService] = None,
        contradiction_service: Optional[ContradictionDetectionService] = None,
        reconciliation_service: Optional[ReconciliationService] = None,
        reporting_service: Optional[ReportingService] = None,
        provenance_tracker: Optional[ProvenanceTracker] = None,
    ) -> None:
        self.provenance_tracker = provenance_tracker or ProvenanceTracker()
        self.ingestion_service = ingestion_service or IngestionService()
        self.extraction_service = extraction_service or ExtractionService()
        self.entity_service = entity_service or EntityResolutionService()
        self.matching_service = matching_service or TransactionMatchingService(entity_service=self.entity_service)
        self.deduplication_service = deduplication_service or DeduplicationService()
        self.contradiction_service = contradiction_service or ContradictionDetectionService()
        self.reconciliation_service = reconciliation_service or ReconciliationService(provenance_tracker=self.provenance_tracker)
        self.reporting_service = reporting_service or ReportingService()

    def execute(self, case_input: CaseInput) -> CaseProcessingResult:
        """Executes the full 8-stage financial controller pipeline for a given case."""
        start_time = time.perf_counter()
        ctx = CaseProcessingContext(case_id=case_input.case_id, case_input=case_input)

        # -------------------------------------------------------------
        # STAGE 1: INGESTION & NORMALIZATION
        # -------------------------------------------------------------
        s1_start = time.perf_counter()
        ev_items: List[Evidence] = list(case_input.evidence_items)

        # Ingest raw files
        for fp in case_input.raw_file_paths:
            res = self.ingestion_service.ingest_file(fp)
            if res.evidence_items:
                ev_items.extend(res.evidence_items)
            elif res.errors:
                ctx.warnings.extend([e.message for e in res.errors])

        # Ingest raw text messages
        for raw_msg in case_input.raw_text_messages:
            text_content = raw_msg.get("text", "")
            s_name = raw_msg.get("source_name", "raw_message.txt")
            res = self.ingestion_service.ingest_text(
                text=text_content,
                source_name=s_name,
                source_type=EvidenceSourceType.WHATSAPP_EXPORT,
            )
            if res.evidence_items:
                ev_items.extend(res.evidence_items)

        ctx.evidence = ev_items
        for ev in ctx.evidence:
            self.provenance_tracker.track_evidence(ev)

        s1_duration = (time.perf_counter() - s1_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.INGESTION,
            status="SUCCESS",
            duration_ms=round(s1_duration, 2),
            items_in=len(case_input.raw_file_paths) + len(case_input.raw_text_messages) + len(case_input.evidence_items),
            items_out=len(ctx.evidence),
        ))

        # -------------------------------------------------------------
        # STAGE 2: CLAIM & TRANSACTION EXTRACTION
        # -------------------------------------------------------------
        s2_start = time.perf_counter()
        extracted_claims: List[Claim] = []
        extracted_txns: List[Transaction] = list(case_input.transactions)

        # Check if claims were precomputed in metadata
        precomputed_claims_data = case_input.metadata.get("precomputed_claims")
        if precomputed_claims_data:
            for c_data in precomputed_claims_data:
                extracted_claims.append(Claim.model_validate(c_data))
        else:
            for ev in ctx.evidence:
                ext_res = self.extraction_service.extract_from_evidence(ev)
                if ext_res.claims:
                    extracted_claims.extend(ext_res.claims)

            # Uploaded bank statement rows are the ledger itself, not assertions to verify.
            bank_evidence_ids = {
                ev.id for ev in ctx.evidence if ev.modality == EvidenceModality.BANK_STATEMENT
            }
            if bank_evidence_ids:
                remaining_claims: List[Claim] = []
                for c in extracted_claims:
                    txn = _bank_claim_to_transaction(c) if c.evidence_id in bank_evidence_ids else None
                    if txn is not None:
                        extracted_txns.append(txn)
                    else:
                        remaining_claims.append(c)
                extracted_claims = remaining_claims

        ctx.claims = extracted_claims
        ctx.transactions = extracted_txns

        for c in ctx.claims:
            self.provenance_tracker.track_claim(c)
        for t in ctx.transactions:
            self.provenance_tracker.track_transaction(t)

        s2_duration = (time.perf_counter() - s2_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.EXTRACTION,
            status="SUCCESS",
            duration_ms=round(s2_duration, 2),
            items_in=len(ctx.evidence),
            items_out=len(ctx.claims) + len(ctx.transactions),
        ))

        # -------------------------------------------------------------
        # STAGE 3: DETERMINISTIC ENTITY RESOLUTION
        # -------------------------------------------------------------
        s3_start = time.perf_counter()
        # Register input entities
        for ent in case_input.entities:
            self.entity_service.register_entity(ent)
        ctx.entities = list(case_input.entities)

        # Resolve counterparty hints for each claim
        claim_ent_map: Dict[str, str] = {}
        for c in ctx.claims:
            res_ent = self.entity_service.resolve_claim(c)
            if res_ent.selected_entity_id:
                claim_ent_map[c.id] = res_ent.selected_entity_id
                if res_ent.selected_entity and res_ent.selected_entity not in ctx.entities:
                    ctx.entities.append(res_ent.selected_entity)

        # Also check pre-provided mapping in metadata
        if "claim_entity_map" in case_input.metadata:
            claim_ent_map.update(case_input.metadata["claim_entity_map"])

        ctx.claim_entity_map = claim_ent_map
        s3_duration = (time.perf_counter() - s3_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.ENTITY_RESOLUTION,
            status="SUCCESS",
            duration_ms=round(s3_duration, 2),
            items_in=len(ctx.claims),
            items_out=len(claim_ent_map),
        ))

        # -------------------------------------------------------------
        # STAGE 4: TRANSACTION MATCHING
        # -------------------------------------------------------------
        s4_start = time.perf_counter()
        precomputed_match_rels = case_input.metadata.get("precomputed_match_relationships")
        if precomputed_match_rels:
            from backend.transaction_matching.result import MatchRelationship
            ctx.match_relationships = [MatchRelationship.model_validate(m) for m in precomputed_match_rels]
        else:
            match_res = self.matching_service.match_records(
                claims=ctx.claims,
                transactions=ctx.transactions,
                claim_entity_map=ctx.claim_entity_map,
            )
            ctx.matching_result = match_res
            ctx.match_relationships = match_res.relationships

        s4_duration = (time.perf_counter() - s4_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.TRANSACTION_MATCHING,
            status="SUCCESS",
            duration_ms=round(s4_duration, 2),
            items_in=len(ctx.claims) + len(ctx.transactions),
            items_out=len(ctx.match_relationships),
        ))

        # -------------------------------------------------------------
        # STAGE 5: CROSS-MODAL EVIDENCE DEDUPLICATION
        # -------------------------------------------------------------
        s5_start = time.perf_counter()
        precomputed_dedup = case_input.metadata.get("precomputed_deduplication_groups")
        if precomputed_dedup:
            from backend.deduplication.result import DeduplicationGroup
            ctx.deduplication_groups = [DeduplicationGroup.model_validate(g) for g in precomputed_dedup]
        else:
            dedup_res = self.deduplication_service.deduplicate_records(
                evidence_items=ctx.evidence,
                claims=ctx.claims,
                transactions=ctx.transactions,
                claim_entity_map=ctx.claim_entity_map,
                match_relationships=ctx.match_relationships,
            )
            ctx.deduplication_result = dedup_res
            ctx.deduplication_groups = dedup_res.groups

        s5_duration = (time.perf_counter() - s5_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.DEDUPLICATION,
            status="SUCCESS",
            duration_ms=round(s5_duration, 2),
            items_in=len(ctx.evidence),
            items_out=len(ctx.deduplication_groups),
        ))

        # -------------------------------------------------------------
        # STAGE 6: DETERMINISTIC CONTRADICTION DETECTION
        # -------------------------------------------------------------
        s6_start = time.perf_counter()
        precomputed_discs = case_input.metadata.get("precomputed_discrepancies")
        if precomputed_discs:
            from backend.domain.discrepancy import Discrepancy
            ctx.discrepancies = [Discrepancy.model_validate(d) for d in precomputed_discs]
        else:
            contra_res = self.contradiction_service.detect_all(
                claims=ctx.claims,
                transactions=ctx.transactions,
                deduplication_groups=ctx.deduplication_groups,
                match_relationships=ctx.match_relationships,
                claim_entity_map=ctx.claim_entity_map,
            )
            ctx.contradiction_result = contra_res
            ctx.discrepancies = contra_res.discrepancies

        for d in ctx.discrepancies:
            self.provenance_tracker.track_discrepancy(d)

        s6_duration = (time.perf_counter() - s6_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.CONTRADICTION_DETECTION,
            status="SUCCESS",
            duration_ms=round(s6_duration, 2),
            items_in=len(ctx.claims) + len(ctx.transactions),
            items_out=len(ctx.discrepancies),
        ))

        # -------------------------------------------------------------
        # STAGE 7: FINANCIAL RECONCILIATION
        # -------------------------------------------------------------
        s7_start = time.perf_counter()
        recon_batch = self.reconciliation_service.reconcile_all(
            claims=ctx.claims,
            transactions=ctx.transactions,
            evidence_items=ctx.evidence,
            deduplication_groups=ctx.deduplication_groups,
            match_relationships=ctx.match_relationships,
            discrepancies=ctx.discrepancies,
            claim_entity_map=ctx.claim_entity_map,
        )
        ctx.reconciliation_result = recon_batch
        if recon_batch.results:
            # The check is about what someone claimed; a leftover bank line shouldn't headline it.
            with_claims = [r for r in recon_batch.results if r.claim_ids]
            ctx.primary_reconciliation = (with_claims or recon_batch.results)[0]

        s7_duration = (time.perf_counter() - s7_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.RECONCILIATION,
            status="SUCCESS",
            duration_ms=round(s7_duration, 2),
            items_in=len(ctx.deduplication_groups) or 1,
            items_out=len(recon_batch.results),
        ))

        # -------------------------------------------------------------
        # STAGE 8: EXPLAINABLE FINANCIAL TRUTH REPORTING
        # -------------------------------------------------------------
        s8_start = time.perf_counter()
        reports = self.reporting_service.build_reports_from_batch(
            batch_result=recon_batch,
            claims=ctx.claims,
            transactions=ctx.transactions,
            evidence=ctx.evidence,
            entities=ctx.entities,
            match_relationships=ctx.match_relationships,
            deduplication_groups=ctx.deduplication_groups,
            discrepancies=ctx.discrepancies,
        )
        ctx.reports = reports
        if reports:
            idx = 0
            if ctx.primary_reconciliation is not None and len(reports) == len(recon_batch.results):
                idx = next((i for i, r in enumerate(recon_batch.results) if r is ctx.primary_reconciliation), 0)
            ctx.primary_report = reports[idx]
            if case_input.case_id:
                ctx.primary_report.case_id = case_input.case_id

        s8_duration = (time.perf_counter() - s8_start) * 1000.0
        ctx.stage_records.append(StageExecutionRecord(
            stage=PipelineStage.REPORTING,
            status="SUCCESS",
            duration_ms=round(s8_duration, 2),
            items_in=len(recon_batch.results),
            items_out=len(reports),
        ))

        # -------------------------------------------------------------
        # SYNTHESIZE FINAL CASE RESULT
        # -------------------------------------------------------------
        total_time = (time.perf_counter() - start_time) * 1000.0
        primary_rec = ctx.primary_reconciliation
        final_status = primary_rec.status.value if primary_rec else "UNVERIFIABLE"
        final_conf = primary_rec.confidence_score if primary_rec else 0.50

        fin_summary = {
            "claimed_amount": primary_rec.expected_amount if primary_rec else None,
            "matched_amount": primary_rec.matched_amount if primary_rec else 0.0,
            "outstanding_amount": primary_rec.outstanding_amount if primary_rec else 0.0,
            "total_reconciled_batch": recon_batch.total_reconciled_amount,
            "total_outstanding_batch": recon_batch.total_outstanding_amount,
            "evidence_count": len(ctx.evidence),
            "claims_count": len(ctx.claims),
            "transactions_count": len(ctx.transactions),
            "discrepancies_count": len(ctx.discrepancies),
        }

        return CaseProcessingResult(
            case_id=case_input.case_id,
            status=final_status,
            confidence_score=final_conf,
            reconciliation=primary_rec,
            report=ctx.primary_report,
            financial_summary=fin_summary,
            stage_records=ctx.stage_records,
            total_execution_time_ms=round(total_time, 2),
            provenance_node_count=len(self.provenance_tracker.audit_trail.nodes),
            warnings=ctx.warnings,
            errors=ctx.errors,
            metadata=case_input.metadata,
        )


def _parse_statement_date(value: Optional[str]) -> Optional["datetime"]:
    from datetime import datetime, timezone

    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _bank_claim_to_transaction(claim: Claim) -> Optional[Transaction]:
    """Converts a claim read from a bank statement row into a verified ledger Transaction."""
    from backend.domain.claim import ClaimType
    from backend.domain.transaction import PaymentMethod, TransactionDirection

    if not claim.claimed_amount or claim.claimed_amount <= 0:
        return None
    if claim.claim_type == ClaimType.PAYMENT_RECEIVED:
        direction = TransactionDirection.CREDIT
    elif claim.claim_type == ClaimType.PAYMENT_SENT:
        direction = TransactionDirection.DEBIT
    else:
        return None

    method_hint = (claim.payment_method_hint or "").upper()
    payment_method = PaymentMethod.__members__.get(method_hint, PaymentMethod.OTHER)

    fields: Dict[str, Any] = {
        "id": claim.id.replace("CLM-", "TXN-", 1),
        "amount": claim.claimed_amount,
        "currency": claim.currency,
        "direction": direction,
        "payment_method": payment_method,
        "bank_reference": claim.reference_id_hint,
        "narration": claim.raw_text_snippet,
        "evidence_ids": [claim.evidence_id],
        "metadata": {"counterparty_hint": claim.counterparty_hint, "source": "bank_statement"},
    }
    ts = _parse_statement_date(claim.claimed_date)
    if ts:
        fields["timestamp"] = ts
    return Transaction(**fields)
