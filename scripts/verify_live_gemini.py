"""Controlled Live Gemini Verification Runner for VERITY Day 17.

Performs:
1. Environment & credential detection (without exposing keys)
2. Live image extraction on local PNG payment screenshot
3. Live messy Hinglish text extraction ("bhai kal maine Rajesh ko 25k bhej diya tha, UTR yaad nahi hai")
4. Pydantic schema validation & domain Claim verification
5. Provenance integrity audit
6. Uncertainty & anti-hallucination verification
7. Deterministic financial pipeline integration

Usage:
    python scripts/verify_live_gemini.py
"""

from __future__ import annotations

import base64
import os
import sys
from datetime import date
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from backend.case_processing.models import CaseInput
from backend.case_processing.pipeline import FinanceControllerPipeline
from backend.domain.claim import ClaimType
from backend.domain.evidence import Evidence, EvidenceModality, EvidenceSourceType
from backend.domain.transaction import Transaction
from backend.extraction.ai_provider import (
    AIExtractionProvider,
    AIProviderConfig,
    AIProviderType,
)
from backend.extraction.result import ExtractionStatus
from backend.ingestion.image_adapter import ImagePaymentScreenshotAdapter


def run_live_gemini_verification() -> None:
    print("=" * 70)
    print("VERITY -- DAY 17 LIVE GEMINI VERIFICATION")
    print("=" * 70)

    # 1. Environment & SDK Inspection
    sdk_installed = False
    try:
        from google import genai
        sdk_installed = True
    except ImportError:
        sdk_installed = False

    # Check for credentials across standard environment variables
    env_keys = ["GEMINI_API_KEY", "GOOGLE_API_KEY", "VERITY_AI_API_KEY"]
    active_env_var = next((k for k in env_keys if os.environ.get(k)), None)
    has_credentials = active_env_var is not None

    configured_model = os.getenv("VERITY_AI_MODEL", "gemini-3.6-flash")

    print(f"\nProvider:                         Google Gemini")
    print(f"Model:                            {configured_model}")
    print(f"SDK Installed (google-genai):     {'YES' if sdk_installed else 'NO'}")
    print(f"Credential Detected:              {'YES (via ' + active_env_var + ')' if has_credentials else 'NO'}")

    if not has_credentials:
        print(f"Actual Network Inference:         NO (Blocked by missing API key)")
        print("\n" + "-" * 70)
        print("SUMMARY REPORT")
        print("-" * 70)
        print("Image extraction:                 NOT RUN / BLOCKED")
        print("Hinglish extraction:              NOT RUN / BLOCKED")
        print("Schema validation:                NOT RUN / BLOCKED")
        print("Provenance:                       NOT RUN / BLOCKED")
        print("Uncertainty handling:             NOT RUN / BLOCKED")
        print("Deterministic pipeline:           NOT RUN / BLOCKED")
        print(f"\nSTATUS: YELLOW (Implementation complete & tested with Mock/Fixtures; Live Gemini blocked pending GEMINI_API_KEY export)")
        print("=" * 70)
        return

    # If credentials exist, perform controlled live tests
    print(f"Actual Network Inference:         YES (Invoking {configured_model})")

    config = AIProviderConfig(
        provider_type=AIProviderType.GEMINI,
        api_key_env_var=active_env_var,
        model_name=configured_model,
    )
    provider = AIExtractionProvider(config=config)

    errors = []

    # -------------------------------------------------------------
    # Test 1: Live Image Extraction (Real Screenshot Fixture)
    # -------------------------------------------------------------
    print("\n--- Test 1: Live Multimodal Image Extraction ---")
    fixture_path = root_dir / "data" / "samples" / "day17" / "fixtures" / "upi_payment_screenshot.png"
    if not fixture_path.exists():
        from scripts.create_day17_fixtures import main as create_fixtures
        create_fixtures()

    adapter = ImagePaymentScreenshotAdapter()
    ingest_res = adapter.ingest_file(fixture_path)
    if ingest_res.status.value != "SUCCESS":
        print(f"[FAIL] Image ingestion failed: {ingest_res.errors}")
        errors.append("Image ingestion failed")
        img_pass = False
    else:
        img_ev = ingest_res.evidence_items[0]
        # Verify base64 bytes are present
        assert "image_bytes_b64" in img_ev.metadata, "Image bytes must be present in metadata"
        print(f"  * Ingested image: {fixture_path.name} ({len(img_ev.metadata['image_bytes_b64'])} base64 chars)")

        img_res = provider.extract(img_ev)
        if img_res.status == ExtractionStatus.SUCCESS and len(img_res.claims) > 0:
            claim = img_res.claims[0]
            print(f"  * Live VLM extracted {len(img_res.claims)} claim(s)")
            print(f"  * Claim Type:   {claim.claim_type.value}")
            print(f"  * Amount:       {claim.claimed_amount}")
            print(f"  * Counterparty: {claim.counterparty_hint}")
            print(f"  * Reference ID: {claim.reference_id_hint}")
            print(f"  * Confidence:   {claim.confidence}")
            print("  [PASS] Live Image Extraction successful")
            img_pass = True
        else:
            print(f"  [FAIL] Image extraction failed: status={img_res.status.value}, errors={img_res.errors}")
            errors.append(f"Image extraction: {img_res.errors}")
            img_pass = False

    # -------------------------------------------------------------
    # Test 2: Live Messy Hinglish Text Extraction
    # -------------------------------------------------------------
    print("\n--- Test 2: Live Messy Hinglish Text Extraction ---")
    raw_text = "bhai kal maine Rajesh ko 25k bhej diya tha, UTR yaad nahi hai"
    text_ev = Evidence(
        id="EVID-LIVE-HINGLISH-001",
        modality=EvidenceModality.MESSAGING_CHAT,
        source_type=EvidenceSourceType.WHATSAPP_EXPORT,
        source_name="whatsapp_chat.txt",
        raw_payload=raw_text,
        language_hint="hinglish",
        metadata={},
    )
    print(f"  * Prompting Gemini with: \"{raw_text}\"")
    text_res = provider.extract(text_ev)

    text_pass = False
    schema_pass = False
    prov_pass = False
    uncertainty_pass = False
    pipeline_pass = False

    if text_res.status == ExtractionStatus.SUCCESS and len(text_res.claims) > 0:
        c = text_res.claims[0]
        text_pass = True
        print(f"  * Live LLM extracted: Type={c.claim_type.value}, Amount={c.claimed_amount}, Counterparty={c.counterparty_hint}")

        # Check Schema
        try:
            assert isinstance(c.claim_type, ClaimType)
            assert c.claimed_amount == 25000.0 or c.claimed_amount == 25000
            schema_pass = True
            print("  [PASS] Schema validation passed")
        except Exception as e:
            print(f"  [FAIL] Schema validation failed: {e}")
            errors.append(f"Schema validation: {e}")

        # Check Provenance
        if c.evidence_id == text_ev.id:
            prov_pass = True
            print(f"  [PASS] Provenance verified (Evidence ID: {c.evidence_id})")
        else:
            print(f"  [FAIL] Provenance mismatch: expected {text_ev.id}, got {c.evidence_id}")
            errors.append("Provenance mismatch")

        # Check Uncertainty (UTR must NOT be hallucinated)
        if c.reference_id_hint is None:
            uncertainty_pass = True
            print("  [PASS] Uncertainty preserved: UTR is None (not hallucinated)")
        else:
            print(f"  [WARN/FAIL] Hallucinated UTR: {c.reference_id_hint}")
            errors.append(f"Hallucinated UTR: {c.reference_id_hint}")

        # -------------------------------------------------------------
        # Test 3: Deterministic Pipeline Integration
        # -------------------------------------------------------------
        print("\n--- Test 3: Deterministic Pipeline Integration ---")
        pipeline = FinanceControllerPipeline()
        case_input = CaseInput(
            case_id="CASE-LIVE-GEMINI-DEMO",
            evidence_items=[text_ev],
            transactions=[
                Transaction(
                    id="TXN-LIVE-001",
                    amount=25000.0,
                    currency="INR",
                    direction="DEBIT",
                    date="2026-08-23",
                    description="UPI/RAJESH",
                    source="Bank_Ledger",
                    reference_id="408219381920",
                )
            ],
        )
        # Execute pipeline where Stage 2 runs extraction and downstream stages reconcile deterministically
        case_output = pipeline.execute(case_input)
        if len(case_output.stage_records) == 8 and case_output.financial_summary["claims_count"] >= 1:
            pipeline_pass = True
            print(f"  * Pipeline completed 8 stages: Status = {case_output.status}")
            print(f"  * Reconciliation Summary: {case_output.financial_summary}")
            print("  [PASS] Clean integration into existing deterministic pipeline")
        else:
            print(f"  [FAIL] Pipeline execution failed: {case_output.error_message}")
            errors.append("Pipeline integration failed")

    else:
        print(f"  [FAIL] Text extraction failed: status={text_res.status.value}, errors={text_res.errors}")
        errors.append(f"Text extraction: {text_res.errors}")

    # -------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------
    all_passed = (
        img_pass and text_pass and schema_pass and prov_pass and uncertainty_pass and pipeline_pass
    )

    print("\n" + "=" * 70)
    print("LIVE GEMINI VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"Provider:                         Google Gemini")
    print(f"Model:                            {configured_model}")
    print(f"SDK:                              google-genai")
    print(f"Credential detected:              YES")
    print(f"Actual network inference:         YES")
    print(f"\nImage extraction:                 {'PASS' if img_pass else 'FAIL'}")
    print(f"Hinglish extraction:              {'PASS' if text_pass else 'FAIL'}")
    print(f"Schema validation:                {'PASS' if schema_pass else 'FAIL'}")
    print(f"Provenance:                       {'PASS' if prov_pass else 'FAIL'}")
    print(f"Uncertainty handling:             {'PASS' if uncertainty_pass else 'FAIL'}")
    print(f"Deterministic pipeline:           {'PASS' if pipeline_pass else 'FAIL'}")

    if errors:
        print(f"\nErrors:                           {', '.join(errors)}")
    else:
        print(f"Errors:                           None")

    final_status = "GREEN" if all_passed else "RED"
    print(f"\nFINAL STATUS: {final_status}")
    print("=" * 70)


if __name__ == "__main__":
    run_live_gemini_verification()
