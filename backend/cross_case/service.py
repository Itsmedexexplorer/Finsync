"""Cross-Case Intelligence & Counterparty Memory Service (Day 18).

Provides deterministic historical intelligence across financial cases:
- Counterparty lifetime history & exposure tracking
- Reference / UTR reuse detection
- Recurring discrepancy pattern identification
- Deterministic cross-case relationship correlation
- Historical risk signals for the AI Finance Controller

Strict Invariants:
1. All signals, correlations, and metrics are derived 100% deterministically from SQL records.
2. Cross-case intelligence MUST NEVER mutate deterministic financial truth (reconciliation status,
   matched amounts, ledger transactions, or evidence).
3. Missing or unique items produce clean empty/first-time profiles with ZERO hallucinations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.cross_case.models import (
    CaseIntelligenceProfile,
    CorrelationRelationshipType,
    CounterpartyHistory,
    CrossCaseCorrelation,
    HistoricalRiskSignal,
    RecurringDiscrepancyPattern,
    ReferenceCorrelation,
)
from backend.storage.database import DatabaseConnection, DatabaseEngine, get_database_engine
from backend.storage.models import (
    ClaimRecord,
    DiscrepancyRecord,
    EntityRecord,
    EvidenceRecord,
    ReconciliationRecordModel,
    TransactionRecord,
)
from backend.storage.repositories.sql.case import SQLCaseRepository
from backend.storage.repositories.sql.claim import SQLClaimRepository
from backend.storage.repositories.sql.discrepancy import SQLDiscrepancyRepository
from backend.storage.repositories.sql.entity import SQLEntityRepository
from backend.storage.repositories.sql.evidence import SQLEvidenceRepository
from backend.storage.repositories.sql.reconciliation import SQLReconciliationRepository
from backend.storage.repositories.sql.transaction import SQLTransactionRepository

logger = logging.getLogger("verity.cross_case.service")


class CrossCaseIntelligenceService:
    """Deterministic intelligence service for cross-case correlation and counterparty memory."""

    def __init__(self, engine: Optional[DatabaseEngine] = None) -> None:
        self.engine = engine or get_database_engine()

    # ------------------------------------------------------------------
    # 1. COUNTERPARTY LIFETIME HISTORY
    # ------------------------------------------------------------------

    def get_counterparty_history(
        self,
        canonical_name_or_id: str,
        exclude_case_id: Optional[str] = None,
        conn: Optional[DatabaseConnection] = None,
    ) -> Optional[CounterpartyHistory]:
        """Builds a historical financial profile for an entity across all persisted cases."""
        if not canonical_name_or_id or not canonical_name_or_id.strip():
            return None

        clean_query = canonical_name_or_id.strip()

        if conn is not None:
            return self._fetch_counterparty_history(clean_query, exclude_case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_counterparty_history(clean_query, exclude_case_id, c)

    def _fetch_counterparty_history(
        self,
        query: str,
        exclude_case_id: Optional[str],
        conn: DatabaseConnection,
    ) -> Optional[CounterpartyHistory]:
        entity_repo = SQLEntityRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)
        disc_repo = SQLDiscrepancyRepository(conn)

        # 1. Locate entity records by ID, canonical name, or identifier
        matching_entities = (
            entity_repo.find_by_name(query)
            or entity_repo.find_by_identifier(query)
        )
        if not matching_entities:
            # Check by direct ID
            single = entity_repo.get(query)
            if single:
                matching_entities = [single]

        if not matching_entities:
            return None

        # Determine canonical representation
        primary_entity = matching_entities[0]
        canonical_name = primary_entity.canonical_name
        all_aliases: Set[str] = set()
        gstin = primary_entity.gstin
        pan = primary_entity.pan
        upi_id = primary_entity.upi_id
        phone = primary_entity.phone

        all_case_ids: Set[str] = set()
        timestamps: List[str] = []

        for e in matching_entities:
            if exclude_case_id and e.case_id == exclude_case_id:
                continue
            all_case_ids.add(e.case_id)
            if e.aliases:
                all_aliases.update(e.aliases)
            if not gstin and e.gstin:
                gstin = e.gstin
            if not pan and e.pan:
                pan = e.pan
            if not upi_id and e.upi_id:
                upi_id = e.upi_id
            if not phone and e.phone:
                phone = e.phone
            if e.created_at:
                timestamps.append(e.created_at)

        sorted_case_ids = sorted(list(all_case_ids))
        case_count = len(sorted_case_ids)

        if case_count == 0:
            return CounterpartyHistory(
                entity_id=primary_entity.id,
                canonical_name=canonical_name,
                aliases=sorted(list(all_aliases)),
                gstin=gstin,
                pan=pan,
                upi_id=upi_id,
                phone=phone,
                case_count=0,
                total_exposure=0.0,
                disputed_exposure=0.0,
                unresolved_exposure=0.0,
                contradiction_count=0,
                previous_case_ids=[],
                discrepancy_types=[],
                first_seen=None,
                last_seen=None,
                historical_risk_signals=[],
            )

        # 2. Fetch authoritative reconciliation metrics across those cases
        reconciliations = recon_repo.list_by_cases(sorted_case_ids)
        total_exposure = 0.0
        disputed_exposure = 0.0
        unresolved_exposure = 0.0
        contradiction_count = 0

        for r in reconciliations:
            exp_amt = r.expected_amount or r.matched_amount or 0.0
            total_exposure += exp_amt
            if r.status in ("CONTRADICTED", "CONTRADICTORY_CLAIMS"):
                contradiction_count += 1
                disputed_exposure += exp_amt
            if r.status in ("PARTIAL", "PARTIALLY_SETTLED", "UNVERIFIABLE", "UNMATCHED"):
                unresolved_exposure += (r.outstanding_amount or 0.0)

        # 3. Collect discrepancy types across cases
        discrepancy_types_set: Set[str] = set()
        for cid in sorted_case_ids:
            discs = disc_repo.list_by_case(cid)
            for d in discs:
                discrepancy_types_set.add(d.discrepancy_type)

        # 4. Formulate deterministic risk signals
        risk_signals: List[str] = []
        if case_count >= 2:
            risk_signals.append(f"Repeat counterparty: appeared in {case_count} historical cases.")
        if contradiction_count > 0:
            risk_signals.append(f"Historical contradiction: {contradiction_count} previous cases had contradictory claims.")
        if unresolved_exposure > 0:
            risk_signals.append(f"Outstanding exposure: ₹{unresolved_exposure:,.2f} unresolved balance across history.")
        if total_exposure >= 100000.0:
            risk_signals.append(f"High cumulative exposure: ₹{total_exposure:,.2f} lifetime transaction volume.")

        timestamps.sort()
        first_seen = timestamps[0] if timestamps else None
        last_seen = timestamps[-1] if timestamps else None

        return CounterpartyHistory(
            entity_id=primary_entity.id,
            canonical_name=canonical_name,
            aliases=sorted(list(all_aliases)),
            gstin=gstin,
            pan=pan,
            upi_id=upi_id,
            phone=phone,
            case_count=case_count,
            total_exposure=round(total_exposure, 2),
            disputed_exposure=round(disputed_exposure, 2),
            unresolved_exposure=round(unresolved_exposure, 2),
            contradiction_count=contradiction_count,
            previous_case_ids=sorted_case_ids,
            discrepancy_types=sorted(list(discrepancy_types_set)),
            first_seen=first_seen,
            last_seen=last_seen,
            historical_risk_signals=risk_signals,
        )

    # ------------------------------------------------------------------
    # 2. REFERENCE / UTR REUSE DETECTION
    # ------------------------------------------------------------------

    def get_reference_history(
        self,
        reference_id: str,
        current_case_id: Optional[str] = None,
        conn: Optional[DatabaseConnection] = None,
    ) -> ReferenceCorrelation:
        """Finds all transactions and claims citing a bank reference/UTR across all cases."""
        if not reference_id or not reference_id.strip():
            return ReferenceCorrelation(
                reference_id=reference_id or "",
                current_case_id=current_case_id,
            )

        ref_clean = reference_id.strip()

        if conn is not None:
            return self._fetch_reference_history(ref_clean, current_case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_reference_history(ref_clean, current_case_id, c)

    def _fetch_reference_history(
        self,
        ref_clean: str,
        current_case_id: Optional[str],
        conn: DatabaseConnection,
    ) -> ReferenceCorrelation:
        txn_repo = SQLTransactionRepository(conn)
        claim_repo = SQLClaimRepository(conn)

        matching_txns = txn_repo.find_by_reference(ref_clean)
        matching_claims = claim_repo.find_by_reference_hint(ref_clean)

        case_ids_set: Set[str] = set()
        txn_ids: List[str] = []
        claim_ids: List[str] = []
        amounts: List[float] = []
        dates: List[str] = []

        for t in matching_txns:
            case_ids_set.add(t.case_id)
            txn_ids.append(t.id)
            if t.amount:
                amounts.append(t.amount)
            if t.timestamp:
                dates.append(t.timestamp)

        for c in matching_claims:
            case_ids_set.add(c.case_id)
            claim_ids.append(c.id)
            if c.claimed_amount:
                amounts.append(c.claimed_amount)
            if c.claimed_date:
                dates.append(c.claimed_date)

        all_case_ids = sorted(list(case_ids_set))
        occurrence_count = len(all_case_ids)

        # Reuse warning triggers if reference appears in >1 distinct case, or in another case besides current
        reuse_warning = False
        if current_case_id:
            other_cases = [cid for cid in all_case_ids if cid != current_case_id]
            reuse_warning = len(other_cases) > 0
        else:
            reuse_warning = occurrence_count > 1

        return ReferenceCorrelation(
            reference_id=ref_clean,
            current_case_id=current_case_id,
            previous_case_ids=all_case_ids,
            transaction_ids=txn_ids,
            claim_ids=claim_ids,
            occurrence_count=occurrence_count,
            reuse_warning=reuse_warning,
            related_amounts=sorted(list(set(amounts))),
            related_dates=sorted(list(set(dates))),
        )

    # ------------------------------------------------------------------
    # 3. RECURRING DISCREPANCY PATTERNS
    # ------------------------------------------------------------------

    def get_recurring_discrepancies(
        self,
        entity_name: Optional[str] = None,
        current_case_id: Optional[str] = None,
        conn: Optional[DatabaseConnection] = None,
    ) -> List[RecurringDiscrepancyPattern]:
        """Analyzes recurring discrepancy categories for an entity or across the database."""
        if conn is not None:
            return self._fetch_recurring_discrepancies(entity_name, current_case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_recurring_discrepancies(entity_name, current_case_id, c)

    def _fetch_recurring_discrepancies(
        self,
        entity_name: Optional[str],
        current_case_id: Optional[str],
        conn: DatabaseConnection,
    ) -> List[RecurringDiscrepancyPattern]:
        disc_repo = SQLDiscrepancyRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)

        # 1. Determine target case IDs
        target_case_ids: Optional[Set[str]] = None
        if entity_name:
            entity_repo = SQLEntityRepository(conn)
            matching_entities = entity_repo.find_by_name(entity_name)
            target_case_ids = {e.case_id for e in matching_entities}
            if current_case_id:
                target_case_ids.discard(current_case_id)
            if not target_case_ids:
                return []

        # 2. Fetch discrepancies
        all_discrepancies: List[DiscrepancyRecord] = []
        if target_case_ids:
            for cid in target_case_ids:
                all_discrepancies.extend(disc_repo.list_by_case(cid))
        else:
            all_discrepancies = disc_repo.list_all(limit=500)
            if current_case_id:
                all_discrepancies = [d for d in all_discrepancies if d.case_id != current_case_id]

        # 3. Group by discrepancy type
        grouped: Dict[str, List[DiscrepancyRecord]] = {}
        for d in all_discrepancies:
            grouped.setdefault(d.discrepancy_type, []).append(d)

        # 4. Synthesize patterns
        patterns: List[RecurringDiscrepancyPattern] = []
        for dtype, records in grouped.items():
            if len(records) >= 1:  # Include any documented discrepancy pattern
                affected_cids = sorted(list({r.case_id for r in records}))
                # Get exposure
                recons = recon_repo.list_by_cases(affected_cids)
                vol = sum((r.expected_amount or r.matched_amount or 0.0) for r in recons)
                severities: Dict[str, int] = {}
                messages: List[str] = []
                for r in records:
                    severities[r.severity] = severities.get(r.severity, 0) + 1
                    if r.message and len(messages) < 3 and r.message not in messages:
                        messages.append(r.message)

                patterns.append(
                    RecurringDiscrepancyPattern(
                        entity_name=entity_name,
                        discrepancy_type=dtype,
                        occurrence_count=len(records),
                        affected_case_ids=affected_cids,
                        total_affected_exposure=round(vol, 2),
                        severity_distribution=severities,
                        sample_messages=messages,
                    )
                )

        patterns.sort(key=lambda p: (p.occurrence_count, p.total_affected_exposure), reverse=True)
        return patterns

    # ------------------------------------------------------------------
    # 4. CROSS-CASE CASE CORRELATIONS
    # ------------------------------------------------------------------

    def get_case_correlations(
        self,
        case_id: str,
        conn: Optional[DatabaseConnection] = None,
    ) -> List[CrossCaseCorrelation]:
        """Discovers deterministic relationships between the given case and historical cases."""
        if conn is not None:
            return self._fetch_case_correlations(case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_case_correlations(case_id, c)

    def _fetch_case_correlations(
        self,
        case_id: str,
        conn: DatabaseConnection,
    ) -> List[CrossCaseCorrelation]:
        entity_repo = SQLEntityRepository(conn)
        txn_repo = SQLTransactionRepository(conn)
        claim_repo = SQLClaimRepository(conn)
        ev_repo = SQLEvidenceRepository(conn)
        recon_repo = SQLReconciliationRepository(conn)

        correlations: List[CrossCaseCorrelation] = []
        seen_pairs: Set[Tuple[str, str, str]] = set()

        # 1. Check Shared Entities
        current_entities = entity_repo.list_by_case(case_id)
        for ent in current_entities:
            matches = entity_repo.find_by_name(ent.canonical_name)
            for m in matches:
                if m.case_id != case_id:
                    key = (m.case_id, CorrelationRelationshipType.SHARED_ENTITY.value, ent.canonical_name)
                    if key not in seen_pairs:
                        seen_pairs.add(key)
                        # Fetch related case recon
                        rel_recon = recon_repo.get_by_case(m.case_id)
                        correlations.append(
                            CrossCaseCorrelation(
                                current_case_id=case_id,
                                related_case_id=m.case_id,
                                relationship_type=CorrelationRelationshipType.SHARED_ENTITY,
                                shared_identifier=ent.canonical_name,
                                deterministic_reason=f"Shared canonical counterparty: '{ent.canonical_name}'",
                                supporting_ids=[ent.id, m.id],
                                related_case_status=rel_recon.status if rel_recon else None,
                                related_case_amount=rel_recon.expected_amount if rel_recon else None,
                            )
                        )

        # 2. Check Shared References / UTRs
        current_txns = txn_repo.list_by_case(case_id)
        for t in current_txns:
            if t.bank_reference:
                matches_t = txn_repo.find_by_reference(t.bank_reference)
                for mt in matches_t:
                    if mt.case_id != case_id:
                        key = (mt.case_id, CorrelationRelationshipType.SHARED_REFERENCE.value, t.bank_reference)
                        if key not in seen_pairs:
                            seen_pairs.add(key)
                            rel_recon = recon_repo.get_by_case(mt.case_id)
                            correlations.append(
                                CrossCaseCorrelation(
                                    current_case_id=case_id,
                                    related_case_id=mt.case_id,
                                    relationship_type=CorrelationRelationshipType.SHARED_REFERENCE,
                                    shared_identifier=t.bank_reference,
                                    deterministic_reason=f"Identical bank reference / UTR: '{t.bank_reference}'",
                                    supporting_ids=[t.id, mt.id],
                                    related_case_status=rel_recon.status if rel_recon else None,
                                    related_case_amount=rel_recon.expected_amount if rel_recon else None,
                                )
                            )

        current_claims = claim_repo.list_by_case(case_id)
        for cl in current_claims:
            if cl.reference_id_hint:
                matches_cl = claim_repo.find_by_reference_hint(cl.reference_id_hint)
                for mcl in matches_cl:
                    if mcl.case_id != case_id:
                        key = (mcl.case_id, CorrelationRelationshipType.SHARED_REFERENCE.value, cl.reference_id_hint)
                        if key not in seen_pairs:
                            seen_pairs.add(key)
                            rel_recon = recon_repo.get_by_case(mcl.case_id)
                            correlations.append(
                                CrossCaseCorrelation(
                                    current_case_id=case_id,
                                    related_case_id=mcl.case_id,
                                    relationship_type=CorrelationRelationshipType.SHARED_REFERENCE,
                                    shared_identifier=cl.reference_id_hint,
                                    deterministic_reason=f"Shared claim reference hint: '{cl.reference_id_hint}'",
                                    supporting_ids=[cl.id, mcl.id],
                                    related_case_status=rel_recon.status if rel_recon else None,
                                    related_case_amount=rel_recon.expected_amount if rel_recon else None,
                                )
                            )

        # 3. Check Shared Cryptographic Evidence Hash
        current_evidence = ev_repo.list_by_case(case_id)
        for ev in current_evidence:
            if ev.sha256_hash:
                matches_ev = ev_repo.find_by_hash(ev.sha256_hash)
                for mev in matches_ev:
                    if mev.case_id != case_id:
                        key = (mev.case_id, CorrelationRelationshipType.SHARED_EVIDENCE_HASH.value, ev.sha256_hash)
                        if key not in seen_pairs:
                            seen_pairs.add(key)
                            rel_recon = recon_repo.get_by_case(mev.case_id)
                            correlations.append(
                                CrossCaseCorrelation(
                                    current_case_id=case_id,
                                    related_case_id=mev.case_id,
                                    relationship_type=CorrelationRelationshipType.SHARED_EVIDENCE_HASH,
                                    shared_identifier=ev.sha256_hash[:12] + "...",
                                    deterministic_reason=f"Exact cryptographic evidence duplicate (SHA-256: {ev.sha256_hash[:8]}...)",
                                    supporting_ids=[ev.id, mev.id],
                                    related_case_status=rel_recon.status if rel_recon else None,
                                    related_case_amount=rel_recon.expected_amount if rel_recon else None,
                                )
                            )

        return correlations

    # ------------------------------------------------------------------
    # 5. HISTORICAL RISK SIGNALS
    # ------------------------------------------------------------------

    def get_historical_risk_signals(
        self,
        case_id: str,
        conn: Optional[DatabaseConnection] = None,
    ) -> List[HistoricalRiskSignal]:
        """Extracts deterministic explainable risk warnings for a case based on history."""
        if conn is not None:
            return self._fetch_historical_risk_signals(case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_historical_risk_signals(case_id, c)

    def _fetch_historical_risk_signals(
        self,
        case_id: str,
        conn: DatabaseConnection,
    ) -> List[HistoricalRiskSignal]:
        entity_repo = SQLEntityRepository(conn)
        txn_repo = SQLTransactionRepository(conn)
        claim_repo = SQLClaimRepository(conn)

        signals: List[HistoricalRiskSignal] = []

        # 1. Counterparty History Signals
        current_entities = entity_repo.list_by_case(case_id)
        for ent in current_entities:
            history = self._fetch_counterparty_history(ent.canonical_name, exclude_case_id=case_id, conn=conn)
            if history and history.case_count > 0:
                # Contradiction signal
                if history.contradiction_count > 0:
                    signals.append(
                        HistoricalRiskSignal(
                            signal_type="REPEAT_CONTRADICTION",
                            severity="CRITICAL",
                            title=f"Recurring Contradiction Risk: {history.canonical_name}",
                            description=(
                                f"Counterparty '{history.canonical_name}' was involved in {history.contradiction_count} "
                                f"previous contradictory cases (Total Disputed: ₹{history.disputed_exposure:,.2f})."
                            ),
                            affected_case_ids=history.previous_case_ids,
                            supporting_ids=[ent.id],
                        )
                    )
                elif history.case_count >= 2:
                    signals.append(
                        HistoricalRiskSignal(
                            signal_type="REPEAT_COUNTERPARTY",
                            severity="INFO",
                            title=f"Known Counterparty: {history.canonical_name}",
                            description=(
                                f"Counterparty '{history.canonical_name}' has appeared in {history.case_count} previous cases "
                                f"with ₹{history.total_exposure:,.2f} historical volume."
                            ),
                            affected_case_ids=history.previous_case_ids,
                            supporting_ids=[ent.id],
                        )
                    )

                if history.unresolved_exposure > 0:
                    signals.append(
                        HistoricalRiskSignal(
                            signal_type="HISTORICAL_UNRESOLVED_BALANCE",
                            severity="WARNING",
                            title=f"Unresolved Historical Balance: {history.canonical_name}",
                            description=(
                                f"Counterparty '{history.canonical_name}' has ₹{history.unresolved_exposure:,.2f} "
                                f"in outstanding/unresolved balances across previous cases."
                            ),
                            affected_case_ids=history.previous_case_ids,
                            supporting_ids=[ent.id],
                        )
                    )

        # 2. Reference Reuse Signals
        current_txns = txn_repo.list_by_case(case_id)
        for t in current_txns:
            if t.bank_reference:
                ref_hist = self._fetch_reference_history(t.bank_reference, current_case_id=case_id, conn=conn)
                if ref_hist.reuse_warning:
                    other_cases = [cid for cid in ref_hist.previous_case_ids if cid != case_id]
                    signals.append(
                        HistoricalRiskSignal(
                            signal_type="REFERENCE_REUSE_DETECTED",
                            severity="CRITICAL",
                            title=f"Duplicate Reference Reuse: {t.bank_reference}",
                            description=(
                                f"Bank reference / UTR '{t.bank_reference}' already appeared in previous case(s): "
                                f"{', '.join(other_cases)}. Potential double-claim or duplicate settlement."
                            ),
                            affected_case_ids=other_cases,
                            supporting_ids=[t.id],
                        )
                    )

        current_claims = claim_repo.list_by_case(case_id)
        for cl in current_claims:
            if cl.reference_id_hint:
                ref_hist = self._fetch_reference_history(cl.reference_id_hint, current_case_id=case_id, conn=conn)
                if ref_hist.reuse_warning:
                    other_cases = [cid for cid in ref_hist.previous_case_ids if cid != case_id]
                    signals.append(
                        HistoricalRiskSignal(
                            signal_type="CLAIM_REFERENCE_REUSE",
                            severity="WARNING",
                            title=f"Claimed Reference Previously Cited: {cl.reference_id_hint}",
                            description=(
                                f"Claim reference hint '{cl.reference_id_hint}' was previously cited in: "
                                f"{', '.join(other_cases)}."
                            ),
                            affected_case_ids=other_cases,
                            supporting_ids=[cl.id],
                        )
                    )

        return signals

    # ------------------------------------------------------------------
    # 6. UNIFIED CASE INTELLIGENCE PROFILE
    # ------------------------------------------------------------------

    def build_case_intelligence_profile(
        self,
        case_id: str,
        conn: Optional[DatabaseConnection] = None,
    ) -> CaseIntelligenceProfile:
        """Assembles the complete institutional memory and cross-case profile for a case."""
        if conn is not None:
            return self._fetch_case_intelligence_profile(case_id, conn)
        else:
            with self.engine.connection() as c:
                return self._fetch_case_intelligence_profile(case_id, c)

    def _fetch_case_intelligence_profile(
        self,
        case_id: str,
        conn: DatabaseConnection,
    ) -> CaseIntelligenceProfile:
        entity_repo = SQLEntityRepository(conn)
        txn_repo = SQLTransactionRepository(conn)
        claim_repo = SQLClaimRepository(conn)

        # 1. Counterparty Histories
        current_entities = entity_repo.list_by_case(case_id)
        histories: List[CounterpartyHistory] = []
        for ent in current_entities:
            h = self._fetch_counterparty_history(ent.canonical_name, exclude_case_id=case_id, conn=conn)
            if h:
                histories.append(h)

        # 2. Reference Correlations
        ref_corrs: List[ReferenceCorrelation] = []
        seen_refs: Set[str] = set()
        for t in txn_repo.list_by_case(case_id):
            if t.bank_reference and t.bank_reference not in seen_refs:
                seen_refs.add(t.bank_reference)
                ref_corrs.append(self._fetch_reference_history(t.bank_reference, current_case_id=case_id, conn=conn))

        for cl in claim_repo.list_by_case(case_id):
            if cl.reference_id_hint and cl.reference_id_hint not in seen_refs:
                seen_refs.add(cl.reference_id_hint)
                ref_corrs.append(self._fetch_reference_history(cl.reference_id_hint, current_case_id=case_id, conn=conn))

        # 3. Recurring Discrepancies
        discrepancies: List[RecurringDiscrepancyPattern] = []
        for ent in current_entities:
            discrepancies.extend(self._fetch_recurring_discrepancies(ent.canonical_name, current_case_id=case_id, conn=conn))

        # 4. Related Cases
        related = self._fetch_case_correlations(case_id, conn=conn)

        # 5. Risk Signals
        signals = self._fetch_historical_risk_signals(case_id, conn=conn)

        return CaseIntelligenceProfile(
            case_id=case_id,
            counterparty_histories=histories,
            reference_correlations=ref_corrs,
            recurring_discrepancies=discrepancies,
            related_cases=related,
            historical_risk_signals=signals,
        )
