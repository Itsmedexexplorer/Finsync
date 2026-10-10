"""Action Generation Factory converting Controller Recommendations into Human Review Tasks."""

from __future__ import annotations

import uuid
from typing import List
from backend.controller.models import ControllerActionType, ControllerRecommendation
from backend.review.models import ReviewAction, ReviewActionStatus, ReviewActionType


class ReviewActionFactory:
    """Instantiates granular ReviewAction objects from deterministic ControllerRecommendations."""

    @classmethod
    def from_recommendations(
        cls,
        recommendations: List[ControllerRecommendation],
    ) -> List[ReviewAction]:
        """Translates controller recommendations into actionable human investigation tasks."""
        actions: List[ReviewAction] = []

        for idx, rec in enumerate(recommendations, start=1):
            act_type = ReviewActionType.REVIEW_EVIDENCE
            if rec.action_type == ControllerActionType.VERIFY_ENTITY:
                act_type = ReviewActionType.VERIFY_ENTITY
            elif rec.action_type == ControllerActionType.VERIFY_TRANSACTION:
                act_type = ReviewActionType.VERIFY_TRANSACTION
            elif rec.action_type == ControllerActionType.INVESTIGATE_CONTRADICTION:
                act_type = ReviewActionType.INVESTIGATE_CONTRADICTION
            elif rec.action_type == ControllerActionType.REQUEST_MISSING_EVIDENCE:
                act_type = ReviewActionType.REQUEST_EVIDENCE
            elif rec.action_type == ControllerActionType.REVIEW_CASE:
                act_type = ReviewActionType.REVIEW_EVIDENCE
            elif rec.action_type == ControllerActionType.CONFIRM_RECONCILIATION:
                act_type = ReviewActionType.CLOSE_REVIEW

            action = ReviewAction(
                action_id=f"ACT-{uuid.uuid4().hex[:8].upper()}",
                action_type=act_type,
                title=rec.title,
                description=f"{rec.explanation} Rationale: {rec.rationale}",
                priority=rec.priority or idx,
                status=ReviewActionStatus.PENDING,
                supporting_ids=list(rec.supporting_ids),
            )
            actions.append(action)

        return actions
