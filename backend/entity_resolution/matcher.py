"""Deterministic Multi-Signal Entity Matching and Scoring Engine for VERITY.

Implements transparent, explainable scoring based on official tax IDs, UPI VPAs,
phone numbers, and normalized name variants. Never collapses ambiguity or ignores conflicts.
"""

from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.domain.entity import Entity
from backend.entity_resolution.normalizer import EntityNormalizer
from backend.entity_resolution.result import (
    EntityCandidate,
    EntityResolutionResult,
    EntityResolutionStatus,
)


class EntityMatcher:
    """Multi-signal deterministic scoring and conflict detection engine."""

    # Signal confidence weights
    WEIGHT_EXACT_GSTIN = 1.00
    WEIGHT_EXACT_PAN = 1.00
    WEIGHT_EXACT_UPI_VPA = 0.98
    WEIGHT_EXACT_PHONE = 0.95
    WEIGHT_EXACT_CANONICAL_NAME = 0.95
    WEIGHT_EXACT_ALIAS = 0.92
    WEIGHT_BUSINESS_NAME_MATCH = 0.85
    WEIGHT_INITIALS_MATCH = 0.65
    WEIGHT_SUBSET_NAME_MATCH = 0.55
    WEIGHT_FUZZY_NAME_MATCH = 0.50

    @classmethod
    def evaluate_candidate(
        cls,
        entity: Entity,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_phone: Optional[str] = None,
        query_tax_id: Optional[str] = None,
    ) -> EntityCandidate:
        """Evaluate a single Entity against query signals, detecting positive matches and contradictions."""
        matched_signals: List[str] = []
        conflicting_signals: List[str] = []
        signal_scores: List[float] = []
        reasons: List[str] = []

        # 1. Evaluate GSTIN & PAN (Strongest Signals)
        if query_tax_id:
            norm_query_tax = EntityNormalizer.normalize_tax_id(query_tax_id)
            norm_ent_gst = EntityNormalizer.normalize_tax_id(entity.gstin) if entity.gstin else None
            norm_ent_pan = EntityNormalizer.normalize_tax_id(entity.pan) if entity.pan else None

            if norm_query_tax and (norm_query_tax == norm_ent_gst or norm_query_tax == norm_ent_pan):
                matched_signals.append("EXACT_TAX_ID")
                signal_scores.append(cls.WEIGHT_EXACT_GSTIN)
                reasons.append(f"Official tax identifier '{query_tax_id}' matches exactly.")
            elif norm_query_tax and (norm_ent_gst or norm_ent_pan):
                conflicting_signals.append("CONFLICTING_TAX_ID")
                reasons.append(f"Tax identifier '{query_tax_id}' conflicts with entity tax record.")

        # 2. Evaluate UPI VPA
        if query_handle:
            norm_query_vpa = EntityNormalizer.normalize_upi_vpa(query_handle)
            ent_vpas = {EntityNormalizer.normalize_upi_vpa(u) for u in entity.upi_ids if u}

            if norm_query_vpa and norm_query_vpa in ent_vpas:
                matched_signals.append("EXACT_UPI_VPA")
                signal_scores.append(cls.WEIGHT_EXACT_UPI_VPA)
                reasons.append(f"UPI VPA '{query_handle}' matches registered handle.")
            elif norm_query_vpa and ent_vpas:
                # Entity has registered VPAs, but this query VPA does not match any of them
                conflicting_signals.append("CONFLICTING_UPI_VPA")
                reasons.append(f"UPI VPA '{query_handle}' conflicts with registered handles.")

        # 3. Evaluate Phone Number
        if query_phone:
            norm_query_phone = EntityNormalizer.normalize_phone(query_phone)
            ent_phones = {EntityNormalizer.normalize_phone(p) for p in entity.phone_numbers if p}

            if norm_query_phone and norm_query_phone in ent_phones:
                matched_signals.append("EXACT_PHONE")
                signal_scores.append(cls.WEIGHT_EXACT_PHONE)
                reasons.append(f"Phone number '{query_phone}' matches registered contact.")
            elif norm_query_phone and ent_phones:
                conflicting_signals.append("CONFLICTING_PHONE")
                reasons.append(f"Phone number '{query_phone}' does not match entity phone.")

        # 4. Evaluate Name and Aliases
        if query_name:
            norm_query_name = EntityNormalizer.normalize_name(query_name)
            norm_canonical = EntityNormalizer.normalize_name(entity.canonical_name)
            norm_aliases = [EntityNormalizer.normalize_name(a) for a in entity.aliases if a]

            query_tokens = EntityNormalizer.extract_core_name_tokens(query_name)
            canonical_tokens = EntityNormalizer.extract_core_name_tokens(entity.canonical_name)

            # A. Exact Canonical Name
            if norm_query_name and norm_query_name == norm_canonical:
                matched_signals.append("EXACT_CANONICAL_NAME")
                signal_scores.append(cls.WEIGHT_EXACT_CANONICAL_NAME)
                reasons.append(f"Canonical name '{entity.canonical_name}' matches query exactly.")

            # B. Exact Alias
            elif norm_query_name and norm_query_name in norm_aliases:
                matched_signals.append("EXACT_ALIAS")
                signal_scores.append(cls.WEIGHT_EXACT_ALIAS)
                reasons.append(f"Trade alias '{query_name}' matches registered alias.")

            # C. Initials Variation (e.g. 'R Kumar' <-> 'Rahul Kumar')
            elif EntityNormalizer.is_initials_match(query_name, entity.canonical_name):
                matched_signals.append("INITIALS_MATCH")
                signal_scores.append(cls.WEIGHT_INITIALS_MATCH)
                reasons.append(f"Name '{query_name}' matches initials for '{entity.canonical_name}'.")

            # D. Business Name Variation (e.g. 'Shree Electronics' <-> 'Shree Electronics Store')
            elif query_tokens and canonical_tokens and query_tokens == canonical_tokens:
                matched_signals.append("BUSINESS_NAME_VARIATION")
                signal_scores.append(cls.WEIGHT_BUSINESS_NAME_MATCH)
                reasons.append(f"Core business name tokens match '{entity.canonical_name}'.")

            # E. Subset Name Match (e.g. 'Rahul' <-> 'Rahul Kumar')
            elif query_tokens and canonical_tokens and set(query_tokens).issubset(set(canonical_tokens)):
                matched_signals.append("SUBSET_NAME_MATCH")
                signal_scores.append(cls.WEIGHT_SUBSET_NAME_MATCH)
                reasons.append(f"Query '{query_name}' is a partial name component of '{entity.canonical_name}'.")

            # F. Fuzzy string similarity check
            else:
                seq = difflib.SequenceMatcher(None, norm_query_name, norm_canonical)
                ratio = seq.ratio()
                if ratio >= 0.85:
                    matched_signals.append("FUZZY_NAME_SIMILARITY")
                    signal_scores.append(cls.WEIGHT_FUZZY_NAME_MATCH * ratio)
                    reasons.append(f"Fuzzy name similarity: {ratio:.2f} with '{entity.canonical_name}'.")
                elif len(query_tokens) >= 2 and len(canonical_tokens) >= 2:
                    # If first name is same but last name differs (e.g. Rahul Kumar vs Rahul Sharma) -> Contradiction!
                    if query_tokens[0] == canonical_tokens[0] and query_tokens[-1] != canonical_tokens[-1]:
                        conflicting_signals.append("DIFFERENT_LAST_NAME")
                        reasons.append(f"First name matches but last name '{query_tokens[-1]}' conflicts with '{canonical_tokens[-1]}'.")

        # Compute overall candidate score
        if not signal_scores:
            final_score = 0.0
            explanation = "No matching identity signals found."
        else:
            max_score = max(signal_scores)
            bonus = 0.03 * (len(signal_scores) - 1) if len(signal_scores) > 1 else 0.0
            final_score = min(1.0, max_score + bonus)
            
            # Penalize if conflicting signals present
            if conflicting_signals:
                final_score = max(0.1, final_score - (0.35 * len(conflicting_signals)))

            explanation = "; ".join(reasons)

        return EntityCandidate(
            entity_id=entity.id,
            canonical_name=entity.canonical_name,
            score=round(final_score, 2),
            matched_signals=matched_signals,
            conflicting_signals=conflicting_signals,
            explanation=explanation,
        )

    @classmethod
    def resolve_candidates(
        cls,
        candidates: List[EntityCandidate],
        claim_id: Optional[str] = None,
        entity_lookup: Optional[Dict[str, Entity]] = None,
    ) -> EntityResolutionResult:
        """Evaluates multiple ranked candidates and produces a safe, unambiguous resolution verdict."""
        if not candidates:
            return EntityResolutionResult(
                claim_id=claim_id,
                status=EntityResolutionStatus.UNRESOLVED,
                selected_entity_id=None,
                score=0.0,
                candidates=[],
                matched_signals=[],
                conflicting_signals=[],
                explanation="No known entities matched the provided identity hints.",
            )

        # Sort candidates descending by score
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        top = ranked[0]
        entity_map = entity_lookup or {}

        # If any top candidate has conflicting signals (e.g. matching phone but conflicting UPI VPA)
        if top.conflicting_signals:
            return EntityResolutionResult(
                claim_id=claim_id,
                status=EntityResolutionStatus.CONFLICTING,
                selected_entity_id=None,
                score=top.score,
                candidates=ranked,
                matched_signals=top.matched_signals,
                conflicting_signals=top.conflicting_signals,
                explanation=f"Conflicting signals detected for '{top.canonical_name}': {top.explanation}",
            )

        # 1. Single Candidate Evaluation
        if len(ranked) == 1:
            if top.score >= 0.90:
                return EntityResolutionResult(
                    claim_id=claim_id,
                    status=EntityResolutionStatus.CONFIRMED,
                    selected_entity_id=top.entity_id,
                    selected_entity=entity_map.get(top.entity_id),
                    score=top.score,
                    candidates=ranked,
                    matched_signals=top.matched_signals,
                    conflicting_signals=[],
                    explanation=f"Unambiguously confirmed identity '{top.canonical_name}': {top.explanation}",
                )
            elif top.score >= 0.60:
                return EntityResolutionResult(
                    claim_id=claim_id,
                    status=EntityResolutionStatus.PROBABLE,
                    selected_entity_id=top.entity_id,
                    selected_entity=entity_map.get(top.entity_id),
                    score=top.score,
                    candidates=ranked,
                    matched_signals=top.matched_signals,
                    conflicting_signals=[],
                    explanation=f"Probable identity match for '{top.canonical_name}': {top.explanation}",
                )
            else:
                return EntityResolutionResult(
                    claim_id=claim_id,
                    status=EntityResolutionStatus.UNRESOLVED,
                    selected_entity_id=None,
                    score=top.score,
                    candidates=ranked,
                    matched_signals=top.matched_signals,
                    conflicting_signals=[],
                    explanation=f"Candidate '{top.canonical_name}' score ({top.score}) is below resolution threshold.",
                )

        # 2. Multiple Candidates Evaluation
        second = ranked[1]

        # Check if top candidate has an exact identifier, canonical name, or exact alias with clear separation
        has_strong_id = any(s in top.matched_signals for s in ("EXACT_TAX_ID", "EXACT_UPI_VPA", "EXACT_PHONE", "EXACT_CANONICAL_NAME", "EXACT_ALIAS"))
        has_exact_name = any(s in top.matched_signals for s in ("EXACT_CANONICAL_NAME", "EXACT_ALIAS"))

        # Case A: Top candidate has exact identifier / full canonical name and gap is >= 0.15
        if has_strong_id and (top.score - second.score) >= 0.15:
            # If top was exact alias/name and second was merely initials/partial
            status = EntityResolutionStatus.CONFIRMED if top.score >= 0.90 else EntityResolutionStatus.PROBABLE
            return EntityResolutionResult(
                claim_id=claim_id,
                status=status,
                selected_entity_id=top.entity_id,
                selected_entity=entity_map.get(top.entity_id),
                score=top.score,
                candidates=ranked,
                matched_signals=top.matched_signals,
                conflicting_signals=[],
                explanation=f"Resolved to highest ranking candidate '{top.canonical_name}': {top.explanation}",
            )

        # Case B: Top and second have close scores or subset name match (e.g. 'Rahul' matching Rahul Kumar & Rahul Sharma)
        # MUST NOT collapse ambiguity!
        names = f"'{top.canonical_name}' (score: {top.score}) and '{second.canonical_name}' (score: {second.score})"
        return EntityResolutionResult(
            claim_id=claim_id,
            status=EntityResolutionStatus.AMBIGUOUS,
            selected_entity_id=None,  # Strictly None
            score=top.score,
            candidates=ranked,
            matched_signals=top.matched_signals,
            conflicting_signals=[],
            explanation=f"Ambiguous identity: Query matches multiple candidate entities with similar confidence: {names}. Human review required.",
        )
