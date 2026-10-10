"""In-memory Entity Registry repository for VERITY.

Maintains normalized lookup indexes for official tax IDs, UPI VPAs, phone numbers,
canonical names, and trade aliases.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from backend.domain.entity import Entity
from backend.entity_resolution.normalizer import EntityNormalizer


class EntityRegistry:
    """Repository and indexed storage for known business and individual entities."""

    def __init__(self, entities: Optional[List[Entity]] = None) -> None:
        self.entities: Dict[str, Entity] = {}
        self.tax_id_index: Dict[str, str] = {}       # normalized tax_id -> entity_id
        self.upi_index: Dict[str, str] = {}          # normalized upi_vpa -> entity_id
        self.phone_index: Dict[str, str] = {}        # normalized phone -> entity_id
        self.name_index: Dict[str, Set[str]] = {}    # normalized canonical name -> set of entity_ids
        self.alias_index: Dict[str, Set[str]] = {}   # normalized alias -> set of entity_ids

        if entities:
            for ent in entities:
                self.register_entity(ent)

    def register_entity(self, entity: Entity) -> None:
        """Add and index an entity in the registry."""
        self.entities[entity.id] = entity

        # Index GSTIN
        if entity.gstin:
            norm_gstin = EntityNormalizer.normalize_tax_id(entity.gstin)
            if norm_gstin:
                self.tax_id_index[norm_gstin] = entity.id

        # Index PAN
        if entity.pan:
            norm_pan = EntityNormalizer.normalize_tax_id(entity.pan)
            if norm_pan:
                self.tax_id_index[norm_pan] = entity.id

        # Index UPI VPAs
        for upi in entity.upi_ids:
            norm_upi = EntityNormalizer.normalize_upi_vpa(upi)
            if norm_upi:
                self.upi_index[norm_upi] = entity.id

        # Index Phone numbers
        for phone in entity.phone_numbers:
            norm_phone = EntityNormalizer.normalize_phone(phone)
            if norm_phone:
                self.phone_index[norm_phone] = entity.id

        # Index Canonical Name
        norm_name = EntityNormalizer.normalize_name(entity.canonical_name)
        if norm_name:
            self.name_index.setdefault(norm_name, set()).add(entity.id)

        # Index Aliases
        for alias in entity.aliases:
            norm_alias = EntityNormalizer.normalize_name(alias)
            if norm_alias:
                self.alias_index.setdefault(norm_alias, set()).add(entity.id)

    def get_by_id(self, entity_id: str) -> Optional[Entity]:
        """Fetch entity by exact entity ID."""
        return self.entities.get(entity_id)

    def find_by_tax_id(self, tax_id: Optional[str]) -> Optional[Entity]:
        """Exact lookup by normalized GSTIN or PAN."""
        if not tax_id:
            return None
        norm = EntityNormalizer.normalize_tax_id(tax_id)
        if norm and norm in self.tax_id_index:
            return self.entities.get(self.tax_id_index[norm])
        return None

    def find_by_upi_vpa(self, upi_vpa: Optional[str]) -> Optional[Entity]:
        """Exact lookup by normalized UPI VPA."""
        if not upi_vpa:
            return None
        norm = EntityNormalizer.normalize_upi_vpa(upi_vpa)
        if norm and norm in self.upi_index:
            return self.entities.get(self.upi_index[norm])
        return None

    def find_by_phone(self, phone: Optional[str]) -> Optional[Entity]:
        """Exact lookup by normalized 10-digit phone number."""
        if not phone:
            return None
        norm = EntityNormalizer.normalize_phone(phone)
        if norm and norm in self.phone_index:
            return self.entities.get(self.phone_index[norm])
        return None

    def get_candidate_entities(
        self,
        query_name: Optional[str] = None,
        query_handle: Optional[str] = None,
        query_phone: Optional[str] = None,
        query_tax_id: Optional[str] = None,
    ) -> List[Entity]:
        """Gathers candidate entities based on exact identifier match or candidate name overlap."""
        candidates: Set[str] = set()

        # 1. Exact tax ID match
        if query_tax_id:
            ent = self.find_by_tax_id(query_tax_id)
            if ent:
                candidates.add(ent.id)

        # 2. Exact UPI VPA match
        if query_handle:
            ent = self.find_by_upi_vpa(query_handle)
            if ent:
                candidates.add(ent.id)

        # 3. Exact Phone match
        if query_phone:
            ent = self.find_by_phone(query_phone)
            if ent:
                candidates.add(ent.id)

        # 4. Exact and partial name/alias matches
        if query_name:
            norm_query = EntityNormalizer.normalize_name(query_name)
            query_tokens = set(EntityNormalizer.extract_core_name_tokens(query_name))

            # Exact name index match
            if norm_query in self.name_index:
                candidates.update(self.name_index[norm_query])
            if norm_query in self.alias_index:
                candidates.update(self.alias_index[norm_query])

            # Check initials or token overlap across all entities if not already found
            for ent in self.entities.values():
                if ent.id in candidates:
                    continue
                
                # Check initials variation (e.g. "R Kumar" <-> "Rahul Kumar")
                if EntityNormalizer.is_initials_match(query_name, ent.canonical_name):
                    candidates.add(ent.id)
                    continue

                for alias in ent.aliases:
                    if EntityNormalizer.is_initials_match(query_name, alias):
                        candidates.add(ent.id)
                        break

                # Check core token overlap
                ent_tokens = set(EntityNormalizer.extract_core_name_tokens(ent.canonical_name))
                if query_tokens and ent_tokens:
                    # If query is a single first name like 'rahul', and entity has 'rahul', add as candidate
                    if query_tokens.intersection(ent_tokens):
                        candidates.add(ent.id)

        return [self.entities[eid] for eid in candidates if eid in self.entities]

    def list_all(self) -> List[Entity]:
        """Return all registered entities."""
        return list(self.entities.values())
