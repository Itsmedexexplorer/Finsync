"""Strongly typed domain models for VERITY Explainable Financial Truth Reports."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.domain.reconciliation import ReconciliationStatus


class ReportStatus(str, Enum):
    """The reported financial reconciliation status."""
    CONFIRMED = "CONFIRMED"
    PARTIALLY_SETTLED = "PARTIALLY_SETTLED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIABLE = "UNVERIFIABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class EntitySummary(BaseModel):
    """Summary of the resolved counterparty identity."""
    entity_id: Optional[str] = Field(default=None, description="Resolved entity ID or None")
    canonical_name: str = Field(default="Unknown", description="Resolved canonical name")
    entity_type: Optional[str] = Field(default=None, description="INDIVIDUAL, BUSINESS, etc.")
    gstin: Optional[str] = Field(default=None, description="GSTIN if known")
    pan: Optional[str] = Field(default=None, description="PAN if known")
    upi_id: Optional[str] = Field(default=None, description="UPI VPA if known")
    phone: Optional[str] = Field(default=None, description="Phone if known")
    resolution_confidence: Optional[float] = Field(default=None, description="Entity match score")
    resolved_via: Optional[str] = Field(default=None, description="Signals used to resolve identity")


class FinancialSummary(BaseModel):
    """Monetary summary of the case and reconciliation."""
    claimed_amount: Optional[float] = Field(default=None, description="Total expected or claimed INR")
    matched_amount: float = Field(default=0.0, description="Total verified ledger credits INR")
    outstanding_amount: float = Field(default=0.0, description="Remaining unsettled balance INR")
    currency: str = Field(default="INR", description="Three-letter ISO currency code")
    claim_count: int = Field(default=0, description="Total number of evaluated claims")
    transaction_count: int = Field(default=0, description="Total number of evaluated transactions")
    evidence_count: int = Field(default=0, description="Total number of root evidence items")


class EvidenceSummaryItem(BaseModel):
    """Summary of an individual evidence artifact."""
    evidence_id: str = Field(..., description="Evidence ID")
    modality: str = Field(..., description="BANK_STATEMENT, INVOICE, MESSAGING_CHAT, PAYMENT_SCREENSHOT, etc.")
    source_name: Optional[str] = Field(default=None, description="Original filename or source identifier")
    source_type: Optional[str] = Field(default=None, description="BANK_CSV, WHATSAPP_EXPORT, ZOHO_INVOICE, etc.")
    sha256_hash: Optional[str] = Field(default=None, description="SHA-256 fingerprint")
    summary: str = Field(default="", description="Human-readable brief summary of content")


class ClaimSummaryItem(BaseModel):
    """Summary of an extracted financial claim."""
    claim_id: str = Field(..., description="Claim ID")
    evidence_id: str = Field(..., description="Root evidence ID")
    claim_type: str = Field(..., description="INVOICE_ISSUED, PAYMENT_SENT, etc.")
    claimed_amount: Optional[float] = Field(default=None, description="Stated amount or None")
    claimed_date: Optional[str] = Field(default=None, description="Stated date string")
    counterparty_hint: Optional[str] = Field(default=None, description="Extracted counterparty name hint")
    reference_id_hint: Optional[str] = Field(default=None, description="Extracted UTR/RRN/Invoice hint")
    confidence: float = Field(default=1.0, description="Extraction confidence")


class TransactionSummaryItem(BaseModel):
    """Summary of a verified bank ledger transaction."""
    transaction_id: str = Field(..., description="Transaction ID")
    amount: float = Field(..., description="Transaction amount INR")
    direction: str = Field(..., description="CREDIT or DEBIT")
    timestamp: Optional[str] = Field(default=None, description="Settlement timestamp")
    bank_reference: Optional[str] = Field(default=None, description="Bank UTR / RRN")
    payment_method: Optional[str] = Field(default=None, description="UPI, IMPS, NEFT, RTGS, etc.")
    counterparty_entity_id: Optional[str] = Field(default=None, description="Linked entity ID")


class MatchingSummary(BaseModel):
    """Summary of transaction matching topology and status."""
    match_relationship_id: Optional[str] = Field(default=None, description="MatchRelationship ID")
    topology: str = Field(default="ONE_TO_ONE", description="ONE_TO_ONE, MANY_TO_ONE, ONE_TO_MANY, PARTIAL")
    status: str = Field(default="MATCHED", description="MATCHED, AMBIGUOUS, CONFLICTING")
    score: float = Field(default=1.0, description="Matching score (0.0 to 1.0)")
    matched_signals: List[str] = Field(default_factory=list, description="Positive match signals")
    conflicting_signals: List[str] = Field(default_factory=list, description="Conflicting signals")
    explanation: str = Field(default="", description="Matching justification")


class ContradictionSummaryItem(BaseModel):
    """Summary of a detected contradiction or discrepancy."""
    discrepancy_id: str = Field(..., description="Discrepancy ID")
    discrepancy_type: str = Field(..., description="AMOUNT_MISMATCH, REFERENCE_MISMATCH, etc.")
    severity: str = Field(..., description="CRITICAL, ERROR, WARNING, INFO")
    message: str = Field(..., description="Explanation of the discrepancy")
    expected_value: Optional[str] = Field(default=None, description="Expected value")
    observed_value: Optional[str] = Field(default=None, description="Observed value")
    involved_evidence_ids: List[str] = Field(default_factory=list, description="Linked evidence IDs")


class ReconciliationSummary(BaseModel):
    """Summary of the final reconciliation decision."""
    reconciliation_id: str = Field(..., description="Reconciliation conclusion ID")
    status: str = Field(..., description="CONFIRMED, PARTIALLY_SETTLED, CONTRADICTED, etc.")
    expected_amount: Optional[float] = Field(default=None, description="Expected amount INR")
    matched_amount: float = Field(default=0.0, description="Substantiated amount INR")
    outstanding_amount: float = Field(default=0.0, description="Outstanding balance INR")
    confidence_score: float = Field(default=1.0, description="Confidence score")
    reason_codes: List[str] = Field(default_factory=list, description="Applied rule codes")


class ConfidenceFactor(BaseModel):
    """Breakdown factor contributing to confidence score."""
    factor_type: str = Field(..., description="Signal or factor name")
    impact: str = Field(..., description="'+', '-', or 'NEUTRAL'")
    description: str = Field(..., description="Explanation of factor contribution")


class UnresolvedItem(BaseModel):
    """Specific unresolved question or ambiguity requiring review."""
    item_type: str = Field(..., description="DISCREPANCY, AMBIGUITY, MISSING_EVIDENCE, etc.")
    description: str = Field(..., description="Details of what remains unresolved")
    severity: str = Field(default="WARNING", description="Severity level")


class ProvenanceReferences(BaseModel):
    """Explicit references to the immutable DAG of domain artifacts."""
    evidence_ids: List[str] = Field(default_factory=list)
    claim_ids: List[str] = Field(default_factory=list)
    transaction_ids: List[str] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)
    match_relationship_ids: List[str] = Field(default_factory=list)
    deduplication_group_ids: List[str] = Field(default_factory=list)
    discrepancy_ids: List[str] = Field(default_factory=list)
    reconciliation_id: Optional[str] = Field(default=None)


class FinancialTruthReport(BaseModel):
    """The canonical, explainable Financial Truth Report for a financial case or event."""
    report_id: str = Field(..., description="Unique report ID, e.g. REP-2026-001")
    case_id: str = Field(..., description="Identifier for the case or event group, e.g. CASE-001")
    status: ReportStatus = Field(..., description="Final financial conclusion status")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence (0.0 to 1.0)")
    title: str = Field(..., description="Concise human-readable case title")
    summary: str = Field(..., description="Executive summary of the financial truth conclusion")
    
    # Subsections
    entity_summary: EntitySummary = Field(..., description="Resolved counterparty details")
    financial_summary: FinancialSummary = Field(..., description="Monetary numbers and counts")
    evidence_summary: List[EvidenceSummaryItem] = Field(default_factory=list, description="Evidence items")
    claims_summary: List[ClaimSummaryItem] = Field(default_factory=list, description="Extracted claims")
    transaction_summary: List[TransactionSummaryItem] = Field(default_factory=list, description="Ledger transactions")
    matching_summary: Optional[MatchingSummary] = Field(default=None, description="Matching topology")
    contradiction_summary: List[ContradictionSummaryItem] = Field(default_factory=list, description="Discrepancies")
    reconciliation_summary: ReconciliationSummary = Field(..., description="Reconciliation metrics")
    confidence_breakdown: List[ConfidenceFactor] = Field(default_factory=list, description="Confidence factors")
    explanation: str = Field(..., description="Deep, deterministic explanation of WHY this conclusion was reached")
    unresolved_items: List[UnresolvedItem] = Field(default_factory=list, description="Uncertainties or open questions")
    recommended_actions: List[str] = Field(default_factory=list, description="Actionable next steps")
    provenance: ProvenanceReferences = Field(..., description="Lineage references across domain nodes")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_text_report(self) -> str:
        """Renders a clean, structured human-readable text report."""
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("VERITY FINANCIAL TRUTH REPORT")
        lines.append("=" * 60)
        lines.append(f"Case ID      : {self.case_id}")
        lines.append(f"Report ID    : {self.report_id}")
        lines.append(f"Status       : {self.status.value}")
        lines.append(f"Confidence   : {int(self.confidence_score * 100)}%")
        lines.append(f"Title        : {self.title}")
        lines.append("")
        
        # Entity
        lines.append("-" * 60)
        lines.append("COUNTERPARTY ENTITY")
        lines.append("-" * 60)
        lines.append(f"Name         : {self.entity_summary.canonical_name}")
        lines.append(f"Entity ID    : {self.entity_summary.entity_id or 'Not resolved'}")
        if self.entity_summary.gstin:
            lines.append(f"GSTIN        : {self.entity_summary.gstin}")
        if self.entity_summary.upi_id:
            lines.append(f"UPI VPA      : {self.entity_summary.upi_id}")
        if self.entity_summary.phone:
            lines.append(f"Phone        : {self.entity_summary.phone}")
        lines.append("")

        # Financial Summary
        lines.append("-" * 60)
        lines.append("FINANCIAL ACCOUNTING SUMMARY")
        lines.append("-" * 60)
        claimed_str = f"INR {self.financial_summary.claimed_amount:,.2f}" if self.financial_summary.claimed_amount is not None else "Not provided"
        lines.append(f"Claimed / Expected Amount  : {claimed_str}")
        lines.append(f"Verified Ledger Matched    : INR {self.financial_summary.matched_amount:,.2f}")
        lines.append(f"Outstanding Balance        : INR {self.financial_summary.outstanding_amount:,.2f}")
        lines.append("")

        # Evidence
        lines.append("-" * 60)
        lines.append(f"SUPPORTING EVIDENCE ({len(self.evidence_summary)} items)")
        lines.append("-" * 60)
        if self.evidence_summary:
            for ev in self.evidence_summary:
                lines.append(f"  * [{ev.modality}] {ev.source_name or ev.evidence_id}: {ev.summary}")
        else:
            lines.append("  * No root evidence items attached.")
        lines.append("")

        # Matching
        if self.matching_summary:
            lines.append("-" * 60)
            lines.append("TRANSACTION MATCHING TOPOLOGY")
            lines.append("-" * 60)
            lines.append(f"Pattern      : {self.matching_summary.topology}")
            lines.append(f"Status       : {self.matching_summary.status} (Score: {self.matching_summary.score:.2f})")
            lines.append(f"Signals      : {', '.join(self.matching_summary.matched_signals) if self.matching_summary.matched_signals else 'None'}")
            lines.append("")

        # Contradictions
        lines.append("-" * 60)
        lines.append(f"CONTRADICTIONS & DISCREPANCIES ({len(self.contradiction_summary)})")
        lines.append("-" * 60)
        if self.contradiction_summary:
            for disc in self.contradiction_summary:
                lines.append(f"  * [{disc.severity}] {disc.discrepancy_type}: {disc.message}")
                if disc.expected_value and disc.observed_value:
                    lines.append(f"    Expected: {disc.expected_value} | Observed: {disc.observed_value}")
        else:
            lines.append("  * No unresolved contradictions detected.")
        lines.append("")

        # Explanation
        lines.append("-" * 60)
        lines.append("EXPLANATION OF FINANCIAL TRUTH")
        lines.append("-" * 60)
        lines.append(self.explanation)
        lines.append("")

        # Confidence Breakdown
        if self.confidence_breakdown:
            lines.append("-" * 60)
            lines.append("CONFIDENCE FACTORS")
            lines.append("-" * 60)
            for factor in self.confidence_breakdown:
                lines.append(f"  {factor.impact} {factor.factor_type}: {factor.description}")
            lines.append("")

        # Recommended Actions
        lines.append("-" * 60)
        lines.append("RECOMMENDED ACTIONS")
        lines.append("-" * 60)
        for act in self.recommended_actions:
            lines.append(f"  -> {act}")
        lines.append("")

        # Provenance References
        lines.append("-" * 60)
        lines.append("PROVENANCE & AUDIT TRAIL REFERENCES")
        lines.append("-" * 60)
        lines.append(f"Evidence IDs       : {', '.join(self.provenance.evidence_ids) if self.provenance.evidence_ids else 'None'}")
        lines.append(f"Claim IDs          : {', '.join(self.provenance.claim_ids) if self.provenance.claim_ids else 'None'}")
        lines.append(f"Transaction IDs    : {', '.join(self.provenance.transaction_ids) if self.provenance.transaction_ids else 'None'}")
        lines.append(f"Discrepancy IDs    : {', '.join(self.provenance.discrepancy_ids) if self.provenance.discrepancy_ids else 'None'}")
        lines.append(f"Reconciliation ID  : {self.provenance.reconciliation_id or 'None'}")
        lines.append("=" * 60)

        return "\n".join(lines)
