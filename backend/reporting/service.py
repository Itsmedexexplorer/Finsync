"""Reporting Service for VERITY Financial Truth Reports."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.deduplication.result import DeduplicationGroup
from backend.domain.claim import Claim
from backend.domain.discrepancy import Discrepancy
from backend.domain.entity import Entity
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.reconciliation.result import BatchReconciliationResult, ReconciliationResult
from backend.reporting.models import FinancialTruthReport
from backend.reporting.report_builder import FinancialTruthReportBuilder
from backend.transaction_matching.result import MatchRelationship


class ReportingService:
    """Service generating structured, explainable financial truth reports and serialization."""

    def build_report(
        self,
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
        """Builds a single FinancialTruthReport from reconciliation output and domain context."""
        return FinancialTruthReportBuilder.build_report(
            reconciliation_result=reconciliation_result,
            claims=claims,
            transactions=transactions,
            evidence=evidence,
            entities=entities,
            match_relationships=match_relationships,
            deduplication_groups=deduplication_groups,
            discrepancies=discrepancies,
            case_id=case_id,
        )

    def build_reports_from_batch(
        self,
        batch_result: BatchReconciliationResult,
        claims: Optional[List[Claim]] = None,
        transactions: Optional[List[Transaction]] = None,
        evidence: Optional[List[Evidence]] = None,
        entities: Optional[List[Entity]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
        deduplication_groups: Optional[List[DeduplicationGroup]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
    ) -> List[FinancialTruthReport]:
        """Builds reports for each ReconciliationResult in a BatchReconciliationResult."""
        reports: List[FinancialTruthReport] = []
        for res in batch_result.results:
            rep = self.build_report(
                reconciliation_result=res,
                claims=claims,
                transactions=transactions,
                evidence=evidence,
                entities=entities,
                match_relationships=match_relationships,
                deduplication_groups=deduplication_groups,
                discrepancies=discrepancies,
                case_id=res.event_id,
            )
            reports.append(rep)
        return reports

    def render_text_report(self, report: FinancialTruthReport) -> str:
        """Renders report into human-readable formatted string."""
        return report.to_text_report()

    def render_json_report(self, report: FinancialTruthReport, indent: int = 2) -> str:
        """Renders report into formatted JSON string."""
        return report.model_dump_json(indent=indent)
