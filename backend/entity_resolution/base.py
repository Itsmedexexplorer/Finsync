"""Entity Resolution subsystem for matching real-world counterparties across aliases and identifiers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from backend.domain.entity import Entity


class BaseEntityResolver(ABC):
    """Abstract interface for entity resolution."""

    @abstractmethod
    def resolve_entity(
        self,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_tax_id: Optional[str] = None,
        query_phone: Optional[str] = None,
    ) -> Optional[Tuple[Entity, float]]:
        """Resolve a query to a canonical Entity along with a confidence score (0.0 to 1.0)."""
        pass


class DeterministicEntityResolver(BaseEntityResolver):
    """Deterministic in-memory entity resolver based on exact and normalized alias matching."""

    def __init__(self, entities: Optional[List[Entity]] = None) -> None:
        self.entities: Dict[str, Entity] = {}
        if entities:
            for ent in entities:
                self.entities[ent.id] = ent

    def add_entity(self, entity: Entity) -> None:
        """Register an entity in the resolver dictionary."""
        self.entities[entity.id] = entity

    def resolve_entity(
        self,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_tax_id: Optional[str] = None,
        query_phone: Optional[str] = None,
    ) -> Optional[Tuple[Entity, float]]:
        """Resolve against known entities using exact tax ID, handle, or alias match."""
        # 1. Exact GSTIN / PAN match (Highest confidence: 1.0)
        if query_tax_id:
            clean_tax = query_tax_id.strip().upper()
            for ent in self.entities.values():
                if (ent.gstin and ent.gstin.upper() == clean_tax) or (ent.pan and ent.pan.upper() == clean_tax):
                    return (ent, 1.0)

        # 2. UPI VPA / Account handle match (Confidence: 0.98)
        if query_handle:
            clean_handle = query_handle.strip().lower()
            for ent in self.entities.values():
                for upi in ent.upi_ids:
                    if upi.strip().lower() == clean_handle:
                        return (ent, 0.98)

        # 3. Phone number match (Confidence: 0.95)
        if query_phone:
            clean_digits = "".join(filter(str.isdigit, query_phone))
            if clean_digits:
                for ent in self.entities.values():
                    for phone in ent.phone_numbers:
                        p_digits = "".join(filter(str.isdigit, phone))
                        if p_digits and (clean_digits.endswith(p_digits[-10:]) or p_digits.endswith(clean_digits[-10:])):
                            return (ent, 0.95)

        # 4. Canonical name or alias match (Confidence: 0.90)
        if query_name:
            clean_name = query_name.strip().lower()
            for ent in self.entities.values():
                if ent.matches_alias_or_handle(clean_name):
                    return (ent, 0.90)
                
                # Check token subset containment
                name_tokens = set(clean_name.split())
                canonical_tokens = set(ent.canonical_name.strip().lower().split())
                if name_tokens and canonical_tokens and (name_tokens.issubset(canonical_tokens) or canonical_tokens.issubset(name_tokens)):
                    return (ent, 0.85)

        return None
