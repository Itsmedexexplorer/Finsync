"""Entity Resolution subsystem for VERITY."""

from backend.entity_resolution.base import BaseEntityResolver, DeterministicEntityResolver
from backend.entity_resolution.matcher import EntityMatcher
from backend.entity_resolution.normalizer import EntityNormalizer
from backend.entity_resolution.registry import EntityRegistry
from backend.entity_resolution.result import (
    EntityCandidate,
    EntityResolutionResult,
    EntityResolutionStatus,
)
from backend.entity_resolution.service import EntityResolutionService

__all__ = [
    "BaseEntityResolver",
    "DeterministicEntityResolver",
    "EntityNormalizer",
    "EntityMatcher",
    "EntityRegistry",
    "EntityCandidate",
    "EntityResolutionResult",
    "EntityResolutionStatus",
    "EntityResolutionService",
]
