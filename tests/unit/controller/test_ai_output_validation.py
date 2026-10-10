"""Unit tests for strict AI Output Validation and Fact Checking."""

import pytest
from backend.controller.ai_explainer import validate_ai_output
from backend.controller.models import ControllerAIResponse


def test_validate_ai_output_valid_facts() -> None:
    context = {
        "status": "CONFIRMED",
        "known_amounts": [35000.0, 0.0],
        "known_entities": ["rahul kumar"],
    }
    ai_resp = ControllerAIResponse(
        summary="Case is fully settled with INR 35,000 reconciled for Rahul Kumar.",
        key_findings=["Clean 1:1 match verified."],
        recommended_actions=["Authorize posting."],
    )
    assert validate_ai_output(ai_resp, context) is True


def test_validate_ai_output_rejects_fabricated_amount() -> None:
    context = {
        "status": "CONFIRMED",
        "known_amounts": [35000.0, 0.0],
    }
    # AI invents INR 99,999 which is not in known_amounts
    fabricated_resp = ControllerAIResponse(
        summary="Payment of INR 99,999 was processed yesterday.",
        key_findings=["Fabricated payment found."],
        recommended_actions=["Review."],
    )
    assert validate_ai_output(fabricated_resp, context) is False


def test_validate_ai_output_rejects_status_contradiction() -> None:
    context = {
        "status": "CONTRADICTED",
        "known_amounts": [20000.0, 18000.0],
    }
    # AI incorrectly claims zero discrepancies on a CONTRADICTED case
    hallucinated_resp = ControllerAIResponse(
        summary="Case is fully settled and confirmed with zero discrepancies detected.",
        key_findings=["All good."],
        recommended_actions=["Authorize."],
    )
    assert validate_ai_output(hallucinated_resp, context) is False
