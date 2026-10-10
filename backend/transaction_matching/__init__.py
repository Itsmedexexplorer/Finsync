"""Transaction Matching subsystem for VERITY."""

from backend.transaction_matching.base import BaseTransactionMatcher, MatchCandidate
from backend.transaction_matching.combiner import CombinationMatcher
from backend.transaction_matching.config import MatchConfig
from backend.transaction_matching.engine import TransactionMatcher
from backend.transaction_matching.result import (
    MatchRelationship,
    MatchRelationshipType,
    MatchStatus,
    TransactionMatchingResult,
)
from backend.transaction_matching.service import TransactionMatchingService
from backend.transaction_matching.signals import PairwiseSignalEvaluator

__all__ = [
    "BaseTransactionMatcher",
    "MatchCandidate",
    "MatchConfig",
    "MatchRelationship",
    "MatchRelationshipType",
    "MatchStatus",
    "TransactionMatchingResult",
    "PairwiseSignalEvaluator",
    "CombinationMatcher",
    "TransactionMatcher",
    "TransactionMatchingService",
]
