"""VERITY Portfolio Aggregation Engine (Day 15).

Converts existing CaseProcessingResult, FinancialTruthReport, ControllerDecision,
and ReviewRecord data into normalized CasePortfolioItem models and computes
portfolio-wide exposure and summary metrics with strictly ZERO double-counting.

Strict Invariants:
1. PORTFOLIO INTELLIGENCE MUST NEVER MODIFY FINANCIAL TRUTH.
2. NO DOUBLE COUNTING: Consume canonical reconciliation / report financial summaries.
3. PRESERVE PROVENANCE: Source case IDs and entity/transaction traces are preserved.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.case_processing.result import CaseProcessingResult
from backend.controller.models import ControllerDecision
from backend.portfolio.models import (
    CaseAssignment,
    CasePortfolioItem,
    PortfolioCaseStatus,
    PortfolioExposure,
    PortfolioPriority,
    PortfolioSummary,
    SLAStatus,
)
from backend.review.models import ReviewRecord, ReviewStatus


class PortfolioAggregator:
    """Deterministic aggregation engine for financial cases."""

    @staticmethod
    def from_case_result(
        case_result: CaseProcessingResult,
        controller_decision: Optional[ControllerDecision] = None,
        review_record: Optional[ReviewRecord] = None,
        assignment: Optional[CaseAssignment] = None,
        sla_status: SLAStatus = SLAStatus.ON_TRACK,
        sla_due_at: Optional[datetime] = None,
        priority: Optional[PortfolioPriority] = None,
    ) -> CasePortfolioItem:
        """Constructs a CasePortfolioItem from a reconciled CaseProcessingResult."""
        case_id = case_result.case_id
        now = datetime.now(timezone.utc)

        # 1. Deterministic Financial Core
        det_status = case_result.status
        conf_score = case_result.confidence_score

        # 2. Financial Metrics (Canonical - Zero Double-Counting)
        report = case_result.report
        fin = report.financial_summary if report else None

        claimed = 0.0
        matched = 0.0
        outstanding = 0.0
        discrepancies_count = 0

        if fin:
            claimed = fin.claimed_amount or 0.0
            matched = fin.matched_amount or 0.0
            outstanding = fin.outstanding_amount or 0.0
            discrepancies_count = len(report.contradiction_summary) if report and report.contradiction_summary else 0
        elif case_result.reconciliation:
            recon = case_result.reconciliation
            claimed = float(recon.expected_amount or 0.0)
            matched = float(recon.matched_amount or 0.0)
            outstanding = float(recon.outstanding_amount or 0.0)
            discrepancies_count = len(recon.discrepancy_ids)

        # Case total financial exposure is the maximum claimed or transactional value
        amount_exposure = claimed if claimed > 0 else (matched + outstanding if matched > 0 else outstanding)
        if amount_exposure == 0.0 and case_result.reconciliation:
            amount_exposure = float(max(case_result.reconciliation.expected_amount or 0.0, case_result.reconciliation.matched_amount or 0.0))

        # Disputed amount: If amount mismatch, the difference; if entity mismatch or severe conflict, the affected amount
        disputed_amount = 0.0
        if det_status == "CONTRADICTED":
            if report and report.contradiction_summary:
                for d in report.contradiction_summary:
                    if d.discrepancy_type == "AMOUNT_MISMATCH" and d.expected_value and d.observed_value:
                        try:
                            disputed_amount = max(disputed_amount, abs(float(d.expected_value) - float(d.observed_value)))
                        except ValueError:
                            disputed_amount = amount_exposure
                    else:
                        disputed_amount = max(disputed_amount, amount_exposure)
            elif case_result.reconciliation and case_result.reconciliation.outstanding_amount > 0 and case_result.reconciliation.matched_amount > 0:
                disputed_amount = case_result.reconciliation.outstanding_amount
            else:
                disputed_amount = amount_exposure

        # Unresolved amount
        unresolved_amount = 0.0
        if det_status == "CONFIRMED":
            unresolved_amount = 0.0
        elif det_status == "PARTIALLY_SETTLED":
            unresolved_amount = max(0.0, claimed - matched)
        elif det_status == "CONTRADICTED":
            unresolved_amount = disputed_amount
        else:
            unresolved_amount = amount_exposure

        partial_amount = max(0.0, claimed - matched) if det_status == "PARTIALLY_SETTLED" else 0.0

        # 3. Intelligence / Controller Layer
        risk_level = "LOW"
        primary_action = "CONFIRM_RECONCILIATION"
        requires_human_review = False
        if report:
            requires_human_review = getattr(report, "requires_human_review", False) or getattr(report, "requires_review", False)
        elif case_result.reconciliation:
            requires_human_review = case_result.reconciliation.status.value != "CONFIRMED" or len(case_result.reconciliation.discrepancy_ids) > 0

        if controller_decision:
            risk_level = controller_decision.risk_level.value
            primary_action = controller_decision.decision.value
            requires_human_review = controller_decision.requires_human_review

        # 4. Review & Operational Status
        human_review_status = "NOT_REQUIRED"
        human_review_decision = None
        portfolio_status = PortfolioCaseStatus.NEW

        if review_record:
            human_review_status = review_record.status.value
            human_review_decision = review_record.decision.value if review_record.decision else None

            if review_record.status == ReviewStatus.CLOSED:
                portfolio_status = PortfolioCaseStatus.CLOSED
            elif review_record.status == ReviewStatus.RESOLVED:
                portfolio_status = PortfolioCaseStatus.RESOLVED
            elif review_record.status == ReviewStatus.ESCALATED:
                portfolio_status = PortfolioCaseStatus.ESCALATED
            elif review_record.status == ReviewStatus.IN_PROGRESS:
                portfolio_status = PortfolioCaseStatus.IN_REVIEW
            elif assignment and assignment.active:
                portfolio_status = PortfolioCaseStatus.ASSIGNED
            elif requires_human_review:
                portfolio_status = PortfolioCaseStatus.TRIAGED
            else:
                portfolio_status = PortfolioCaseStatus.NEW
        else:
            if assignment and assignment.active:
                portfolio_status = PortfolioCaseStatus.ASSIGNED
            elif requires_human_review:
                portfolio_status = PortfolioCaseStatus.TRIAGED
            else:
                portfolio_status = PortfolioCaseStatus.NEW

        # 5. Reviewer Assignment
        assigned_reviewer_id = assignment.reviewer_id if (assignment and assignment.active) else None
        assigned_reviewer_name = assignment.reviewer_name if (assignment and assignment.active) else None

        # 6. Priority Derivation
        if priority is None:
            if risk_level == "CRITICAL" or sla_status == SLAStatus.OVERDUE:
                priority = PortfolioPriority.CRITICAL
            elif risk_level == "HIGH" or sla_status == SLAStatus.DUE_SOON:
                priority = PortfolioPriority.HIGH
            elif risk_level == "MEDIUM" or requires_human_review:
                priority = PortfolioPriority.MEDIUM
            else:
                priority = PortfolioPriority.LOW

        # 7. Domain References and Counts
        entity_ids: List[str] = []
        transaction_ids: List[str] = []
        discrepancy_ids: List[str] = []
        evidence_count = 0
        claim_count = 0
        transaction_count = 0

        if report:
            evidence_count = len(report.evidence_summary)
            if report.provenance:
                entity_ids = list(report.provenance.claim_ids) # Traceable
                transaction_ids = list(report.provenance.transaction_ids)
                discrepancy_ids = list(report.provenance.discrepancy_ids)
            if report.contradiction_summary:
                discrepancy_ids = [getattr(d, "discrepancy_id", getattr(d, "id", str(d))) for d in report.contradiction_summary]
        elif case_result.reconciliation:
            recon = case_result.reconciliation
            evidence_count = len(recon.evidence_ids)
            claim_count = len(recon.claim_ids)
            transaction_count = len(recon.transaction_ids)
            transaction_ids = list(recon.transaction_ids)
            discrepancy_ids = list(recon.discrepancy_ids)

        unresolved_issue_count = len(discrepancy_ids)
        if det_status in ("AMBIGUOUS", "UNVERIFIABLE", "PARTIALLY_SETTLED"):
            unresolved_issue_count = max(unresolved_issue_count, 1)

        title = report.title if report else f"Case {case_id}"
        summary = report.summary if report else f"Reconciliation status: {det_status}"

        return CasePortfolioItem(
            case_id=case_id,
            created_at=now,
            updated_at=now,
            deterministic_status=det_status,
            confidence_score=conf_score,
            human_review_status=human_review_status,
            human_review_decision=human_review_decision,
            portfolio_status=portfolio_status,
            risk_level=risk_level,
            priority=priority,
            primary_action=primary_action,
            requires_human_review=requires_human_review,
            assigned_reviewer_id=assigned_reviewer_id,
            assigned_reviewer_name=assigned_reviewer_name,
            sla_status=sla_status,
            sla_due_at=sla_due_at,
            amount_exposure=amount_exposure,
            disputed_amount=disputed_amount,
            unresolved_amount=unresolved_amount,
            partial_amount=partial_amount,
            matched_amount=matched,
            entity_ids=entity_ids,
            transaction_ids=transaction_ids,
            discrepancy_ids=discrepancy_ids,
            evidence_count=evidence_count,
            claim_count=claim_count,
            transaction_count=transaction_count,
            unresolved_issue_count=unresolved_issue_count,
            source_case_id=case_id,
            last_activity_at=now,
            title=title,
            summary=summary,
        )

    @staticmethod
    def aggregate_summary(items: List[CasePortfolioItem]) -> PortfolioSummary:
        """Aggregates a collection of portfolio items into an executive summary."""
        total_cases = len(items)
        new_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.NEW)
        in_review_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.IN_REVIEW)
        waiting_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.WAITING_FOR_EVIDENCE)
        escalated_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.ESCALATED)
        resolved_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.RESOLVED)
        closed_cases = sum(1 for i in items if i.portfolio_status == PortfolioCaseStatus.CLOSED)
        open_cases = total_cases - (resolved_cases + closed_cases)

        critical_cases = sum(1 for i in items if i.risk_level == "CRITICAL")
        high_risk_cases = sum(1 for i in items if i.risk_level == "HIGH")
        medium_risk_cases = sum(1 for i in items if i.risk_level == "MEDIUM")
        low_risk_cases = sum(1 for i in items if i.risk_level in ("LOW", "NONE"))

        total_exposure = sum(i.amount_exposure for i in items)
        total_disputed = sum(i.disputed_amount for i in items)
        total_unresolved = sum(i.unresolved_amount for i in items)
        total_partial = sum(i.partial_amount for i in items)

        overdue_cases = sum(1 for i in items if i.sla_status == SLAStatus.OVERDUE)
        due_soon_cases = sum(1 for i in items if i.sla_status == SLAStatus.DUE_SOON)
        assigned_cases = sum(1 for i in items if i.assigned_reviewer_id is not None)
        unassigned_cases = total_cases - assigned_cases

        return PortfolioSummary(
            total_cases=total_cases,
            new_cases=new_cases,
            open_cases=open_cases,
            in_review_cases=in_review_cases,
            waiting_for_evidence_cases=waiting_cases,
            escalated_cases=escalated_cases,
            resolved_cases=resolved_cases,
            closed_cases=closed_cases,
            critical_cases=critical_cases,
            high_risk_cases=high_risk_cases,
            medium_risk_cases=medium_risk_cases,
            low_risk_cases=low_risk_cases,
            total_exposure=round(total_exposure, 2),
            total_disputed_amount=round(total_disputed, 2),
            total_unresolved_amount=round(total_unresolved, 2),
            total_partial_amount=round(total_partial, 2),
            overdue_cases=overdue_cases,
            due_soon_cases=due_soon_cases,
            assigned_cases=assigned_cases,
            unassigned_cases=unassigned_cases,
        )

    @staticmethod
    def aggregate_exposure(items: List[CasePortfolioItem]) -> PortfolioExposure:
        """Aggregates financial exposure breakdowns across the portfolio."""
        total_exp = sum(i.amount_exposure for i in items)
        disputed_exp = sum(i.disputed_amount for i in items)
        unresolved_exp = sum(i.unresolved_amount for i in items)
        partial_exp = sum(i.partial_amount for i in items)
        confirmed_exp = sum(i.matched_amount for i in items if i.deterministic_status == "CONFIRMED")

        by_risk: Dict[str, float] = {}
        for i in items:
            by_risk[i.risk_level] = round(by_risk.get(i.risk_level, 0.0) + i.amount_exposure, 2)

        by_status: Dict[str, float] = {}
        for i in items:
            stat = i.portfolio_status.value
            by_status[stat] = round(by_status.get(stat, 0.0) + i.amount_exposure, 2)

        return PortfolioExposure(
            total_exposure=round(total_exp, 2),
            disputed_exposure=round(disputed_exp, 2),
            unresolved_exposure=round(unresolved_exp, 2),
            partial_exposure=round(partial_exp, 2),
            confirmed_exposure=round(confirmed_exp, 2),
            exposure_by_risk=by_risk,
            exposure_by_status=by_status,
        )
