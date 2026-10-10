"""Deterministic Cross-Modal Deduplication Engine for VERITY.

Clusters and groups multimodal financial evidence into canonical event groups without
deleting raw evidence or falsely merging distinct financial events.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.deduplication.config import DeduplicationConfig
from backend.deduplication.fingerprint import EventFingerprint
from backend.deduplication.result import (
    DeduplicationGroup,
    DeduplicationResult,
    DeduplicationStatus,
)
from backend.deduplication.signals import DeduplicationSignalEvaluator
from backend.domain.claim import Claim
from backend.domain.evidence import Evidence
from backend.domain.transaction import Transaction
from backend.transaction_matching.result import MatchRelationship, MatchRelationshipType


class DeduplicationEngine:
    """Multi-phase cross-modal evidence and financial event deduplicator."""

    def __init__(self, config: Optional[DeduplicationConfig] = None) -> None:
        self.config = config or DeduplicationConfig()

    def deduplicate(
        self,
        evidence_items: List[Evidence],
        claims: Optional[List[Claim]] = None,
        transactions: Optional[List[Transaction]] = None,
        claim_entity_map: Optional[Dict[str, str]] = None,
        match_relationships: Optional[List[MatchRelationship]] = None,
    ) -> DeduplicationResult:
        """Executes full cross-modal deduplication pipeline."""
        claims_list = claims or []
        txns_list = transactions or []
        entity_map = claim_entity_map or {}
        relationships_list = match_relationships or []

        groups: List[DeduplicationGroup] = []
        assigned_evidence_ids: Set[str] = set()
        assigned_claim_ids: Set[str] = set()
        assigned_txn_ids: Set[str] = set()

        claim_by_id = {c.id: c for c in claims_list}
        evidence_by_id = {e.id: e for e in evidence_items}
        txn_by_id = {t.id: t for t in txns_list}

        # -----------------------------------------------------------------
        # Phase 1: Cryptographic Content Duplication (Identical SHA-256)
        # -----------------------------------------------------------------
        hash_clusters: Dict[str, List[Evidence]] = {}
        for ev in evidence_items:
            if ev.content_hash:
                hash_clusters.setdefault(ev.content_hash, []).append(ev)

        for content_hash, cluster in hash_clusters.items():
            if len(cluster) > 1:
                ev_ids = [e.id for e in cluster]
                gid = f"GRP-HASH-{uuid.uuid4().hex[:8]}"
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT,
                    member_evidence_ids=ev_ids,
                    member_claim_ids=[c.id for c in claims_list if c.evidence_id in ev_ids],
                    candidate_transaction_ids=[],
                    canonical_event_candidate={"content_hash": content_hash},
                    score=1.0,
                    matched_signals=["EXACT_CONTENT_HASH"],
                    conflicting_signals=[],
                    explanation=f"Exact cryptographic payload duplicate: {len(cluster)} evidence items share identical SHA-256 hash.",
                ))
                assigned_evidence_ids.update(ev_ids)

        # -----------------------------------------------------------------
        # Phase 2: Match Relationship Event Grouping (Day 5 Links)
        # -----------------------------------------------------------------
        for rel in relationships_list:
            # Gather members
            m_claim_ids = [cid for cid in rel.source_claim_ids if cid in claim_by_id]
            m_txn_ids = [tid for tid in rel.target_transaction_ids if tid in txn_by_id]

            m_ev_ids: Set[str] = set()
            for cid in m_claim_ids:
                m_ev_ids.add(claim_by_id[cid].evidence_id)
            for tid in m_txn_ids:
                m_ev_ids.update(txn_by_id[tid].evidence_ids)

            # Also check for supporting screenshots / chat evidence with same UTR or entity
            for ev in evidence_items:
                if ev.id not in m_ev_ids:
                    # Check claims derived from this evidence
                    ev_claims = [c for c in claims_list if c.evidence_id == ev.id]
                    for ec in ev_claims:
                        if ec.reference_id_hint and any(
                            EventFingerprint.get_reference_key(ec.reference_id_hint) == EventFingerprint.get_reference_key(txn_by_id[tid].bank_reference)
                            for tid in m_txn_ids if txn_by_id[tid].bank_reference
                        ):
                            m_ev_ids.add(ev.id)
                            m_claim_ids.append(ec.id)

            if m_ev_ids or m_claim_ids or m_txn_ids:
                gid = f"GRP-EVT-{uuid.uuid4().hex[:8]}"
                status = (
                    DeduplicationStatus.SAME_EVENT
                    if not rel.conflicting_signals
                    else DeduplicationStatus.POSSIBLE_DUPLICATE
                )

                canonical_event = {
                    "amount": rel.matched_amount,
                    "entity_id": rel.entity_id,
                    "relationship_type": rel.relationship_type.value,
                }
                if m_txn_ids:
                    primary_txn = txn_by_id[m_txn_ids[0]]
                    canonical_event["reference"] = primary_txn.bank_reference
                    canonical_event["payment_method"] = primary_txn.payment_method.value
                    canonical_event["direction"] = primary_txn.direction.value

                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=status,
                    member_evidence_ids=list(m_ev_ids),
                    member_claim_ids=list(set(m_claim_ids)),
                    candidate_transaction_ids=m_txn_ids,
                    canonical_event_candidate=canonical_event,
                    score=rel.score,
                    matched_signals=rel.matched_signals + ["MATCH_RELATIONSHIP_GROUPING"],
                    conflicting_signals=rel.conflicting_signals,
                    explanation=f"Cross-Modal Event Group ({len(m_ev_ids)} evidence artifacts): {rel.explanation}",
                    entity_id=rel.entity_id,
                ))

                assigned_evidence_ids.update(m_ev_ids)
                assigned_claim_ids.update(m_claim_ids)
                assigned_txn_ids.update(m_txn_ids)

        # -----------------------------------------------------------------
        # Phase 3: Exact Reference (UTR / RRN) Cross-Modal Clustering
        # -----------------------------------------------------------------
        ref_clusters: Dict[str, Dict[str, Any]] = {}

        for ev in evidence_items:
            if ev.id in assigned_evidence_ids:
                continue
            ev_claims = [c for c in claims_list if c.evidence_id == ev.id and c.reference_id_hint]
            for c in ev_claims:
                ref_key = EventFingerprint.get_reference_key(c.reference_id_hint)
                if ref_key:
                    ref_clusters.setdefault(ref_key, {"ev_ids": set(), "claim_ids": set(), "txn_ids": set()})
                    ref_clusters[ref_key]["ev_ids"].add(ev.id)
                    ref_clusters[ref_key]["claim_ids"].add(c.id)

        for t in txns_list:
            if t.id in assigned_txn_ids:
                continue
            ref_key = EventFingerprint.get_reference_key(t.bank_reference)
            if ref_key:
                ref_clusters.setdefault(ref_key, {"ev_ids": set(), "claim_ids": set(), "txn_ids": set()})
                ref_clusters[ref_key]["txn_ids"].add(t.id)
                ref_clusters[ref_key]["ev_ids"].update(t.evidence_ids)

        for ref_key, cluster in ref_clusters.items():
            ev_ids = list(cluster["ev_ids"])
            c_ids = list(cluster["claim_ids"])
            t_ids = list(cluster["txn_ids"])

            if len(ev_ids) > 1 or (ev_ids and t_ids):
                # Evaluate signals across cluster items
                gid = f"GRP-REF-{uuid.uuid4().hex[:8]}"
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.SAME_EVENT,
                    member_evidence_ids=ev_ids,
                    member_claim_ids=c_ids,
                    candidate_transaction_ids=t_ids,
                    canonical_event_candidate={"reference_key": ref_key},
                    score=1.0,
                    matched_signals=["EXACT_REFERENCE"],
                    conflicting_signals=[],
                    explanation=f"Cross-modal correlation via common reference key '{ref_key}' across {len(ev_ids)} evidence items.",
                ))
                assigned_evidence_ids.update(ev_ids)
                assigned_claim_ids.update(c_ids)
                assigned_txn_ids.update(t_ids)

        # -----------------------------------------------------------------
        # Phase 4: Entity + Amount + Date Window / Ambiguity Clustering
        # -----------------------------------------------------------------
        remaining_evs = [e for e in evidence_items if e.id not in assigned_evidence_ids]
        remaining_claims = [c for c in claims_list if c.id not in assigned_claim_ids]
        remaining_txns = [t for t in txns_list if t.id not in assigned_txn_ids]

        for t in remaining_txns:
            if t.id in assigned_txn_ids:
                continue
            t_ent = t.origin_entity_id or t.destination_entity_id
            t_amt = t.amount
            t_date = t.known_timestamp.strftime("%Y-%m-%d") if t.known_timestamp else None

            # Find matching candidate claims on amount
            matching_candidate_claims: List[Tuple[Claim, float, List[str], List[str], str]] = []
            for c in remaining_claims:
                if c.id in assigned_claim_ids:
                    continue
                c_ent = entity_map.get(c.id)
                c_amt = c.claimed_amount
                c_date = c.claimed_date

                score, ms, cs, exp = DeduplicationSignalEvaluator.evaluate_correlation(
                    ref_a=c.reference_id_hint,
                    ref_b=t.bank_reference,
                    amt_a=c_amt,
                    amt_b=t_amt,
                    ent_a=c_ent,
                    ent_b=t_ent,
                    date_a=c_date,
                    date_b=t_date,
                    config=self.config,
                )
                if "EXACT_AMOUNT_MATCH" in ms and not cs:
                    matching_candidate_claims.append((c, score, ms, cs, exp))

            # If multiple unreferenced claims match the same transaction amount -> AMBIGUOUS!
            if len(matching_candidate_claims) > 1:
                gid = f"GRP-AMB-{uuid.uuid4().hex[:8]}"
                m_evs = {c.evidence_id for c, _, _, _, _ in matching_candidate_claims} | set(t.evidence_ids)
                m_cids = [c.id for c, _, _, _, _ in matching_candidate_claims]
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.AMBIGUOUS,
                    member_evidence_ids=list(m_evs),
                    member_claim_ids=m_cids,
                    candidate_transaction_ids=[t.id],
                    canonical_event_candidate={"amount": t_amt},
                    score=0.75,
                    matched_signals=["EXACT_AMOUNT_MATCH", "MULTIPLE_CANDIDATE_SCREENSHOTS"],
                    conflicting_signals=[],
                    explanation=f"Ambiguous cross-modal evidence: {len(matching_candidate_claims)} unreferenced assertions match bank credit of ₹{t_amt:,.2f}.",
                ))
                assigned_evidence_ids.update(m_evs)
                assigned_claim_ids.update(m_cids)
                assigned_txn_ids.add(t.id)

            elif len(matching_candidate_claims) == 1:
                c, score, ms, cs, exp = matching_candidate_claims[0]
                gid = f"GRP-EAD-{uuid.uuid4().hex[:8]}"
                m_evs = {c.evidence_id} | set(t.evidence_ids)
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.SAME_EVENT if score >= self.config.min_score_same_event else DeduplicationStatus.POSSIBLE_DUPLICATE,
                    member_evidence_ids=list(m_evs),
                    member_claim_ids=[c.id],
                    candidate_transaction_ids=[t.id],
                    canonical_event_candidate={"amount": t_amt, "entity_id": entity_map.get(c.id)},
                    score=score,
                    matched_signals=ms,
                    conflicting_signals=cs,
                    explanation=f"Corroborated event group: {exp}",
                ))
                assigned_evidence_ids.update(m_evs)
                assigned_claim_ids.add(c.id)
                assigned_txn_ids.add(t.id)

        # -----------------------------------------------------------------
        # Phase 5: Distinct Standalone Events
        # -----------------------------------------------------------------
        # Standalone remaining transactions
        for t in txns_list:
            if t.id not in assigned_txn_ids:
                gid = f"GRP-TXN-{uuid.uuid4().hex[:8]}"
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.DISTINCT_EVENT,
                    member_evidence_ids=t.evidence_ids,
                    member_claim_ids=[],
                    candidate_transaction_ids=[t.id],
                    canonical_event_candidate={
                        "amount": t.amount,
                        "reference": t.bank_reference,
                        "direction": t.direction.value,
                    },
                    score=1.0,
                    matched_signals=["STANDALONE_LEDGER_TRANSACTION"],
                    conflicting_signals=[],
                    explanation=f"Standalone distinct ledger transaction of ₹{t.amount:,.2f}.",
                ))
                assigned_txn_ids.add(t.id)
                assigned_evidence_ids.update(t.evidence_ids)

        # Standalone remaining evidence items
        for ev in evidence_items:
            if ev.id not in assigned_evidence_ids:
                gid = f"GRP-EV-{uuid.uuid4().hex[:8]}"
                ev_claims = [c.id for c in claims_list if c.evidence_id == ev.id]
                groups.append(DeduplicationGroup(
                    group_id=gid,
                    status=DeduplicationStatus.DISTINCT_EVENT,
                    member_evidence_ids=[ev.id],
                    member_claim_ids=ev_claims,
                    candidate_transaction_ids=[],
                    canonical_event_candidate={"modality": ev.modality.value},
                    score=1.0,
                    matched_signals=["STANDALONE_EVIDENCE_RECORD"],
                    conflicting_signals=[],
                    explanation=f"Standalone evidence record ({ev.modality.value}).",
                ))
                assigned_evidence_ids.add(ev.id)

        # Metrics aggregation
        content_dup_count = len([g for g in groups if g.status == DeduplicationStatus.DUPLICATE_EVIDENCE_CONTENT])
        distinct_count = len([g for g in groups if g.status == DeduplicationStatus.DISTINCT_EVENT])
        ambiguous_count = len([g for g in groups if g.status == DeduplicationStatus.AMBIGUOUS])

        metrics = {
            "total_groups": len(groups),
            "same_event_groups": len([g for g in groups if g.status == DeduplicationStatus.SAME_EVENT]),
            "possible_duplicate_groups": len([g for g in groups if g.status == DeduplicationStatus.POSSIBLE_DUPLICATE]),
            "content_duplicate_groups": content_dup_count,
            "distinct_event_groups": distinct_count,
            "ambiguous_groups": ambiguous_count,
            "total_evidence_evaluated": len(evidence_items),
        }

        return DeduplicationResult(
            groups=groups,
            distinct_event_count=distinct_count,
            content_duplicate_count=content_dup_count,
            ambiguous_count=ambiguous_count,
            metrics=metrics,
        )
