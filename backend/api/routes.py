"""FastAPI route definitions with security validation and structured responses."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.dependencies import (
    CaseStore,
    InMemoryCaseStore,
    get_case_service,
    get_case_store,
)
from backend.api.models import (
    BenchmarkCaseSummary,
    BenchmarkRunResponse,
    CaseCreateRequest,
    CaseResponse,
    DemoCaseSummaryResponse,
    HealthResponse,
    InfoResponse,
    ProvenanceGraphResponse,
    ReadinessResponse,
    TextEvidenceRequest,
)
from backend.api.security import SecurityValidator
from backend.api.serialization import (
    serialize_case_result,
    serialize_provenance_graph,
)
from backend.case_processing.models import CaseInput
from backend.case_processing.service import CaseProcessingService
from backend.config import Settings, get_settings

router = APIRouter()


def require_demo_enabled() -> None:
    """Demo scenarios and the synthetic benchmark are hidden from real users by default."""
    if not get_settings().enable_demo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


# -------------------------------------------------------------
# SYSTEM, HEALTH & READINESS ENDPOINTS
# -------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["System Health"])
def health_check() -> HealthResponse:
    """Returns basic system liveness status."""
    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse, tags=["System Health"])
def readiness_check(
    store: CaseStore = Depends(get_case_store),
    service: CaseProcessingService = Depends(get_case_service),
) -> ReadinessResponse:
    """Returns readiness check status evaluating all internal core subsystems."""
    from backend.api.dependencies import get_storage_service
    settings = get_settings()
    benchmark_file = Path(settings.benchmark_path)
    benchmark_ok = benchmark_file.exists()
    case_store_ok = store is not None
    pipeline_ok = service.pipeline is not None

    storage = get_storage_service()
    storage_health = storage.check_health()
    db_ok = storage_health.get("status") == "HEALTHY"

    all_ready = benchmark_ok and case_store_ok and pipeline_ok and db_ok

    return ReadinessResponse(
        status="ready" if all_ready else "unready",
        service="verity",
        environment=settings.env,
        config_valid=True,
        case_store_ready=case_store_ok,
        database_ready=db_ok,
        audit_store_ready=db_ok,
        benchmark_available=benchmark_ok,
        pipeline_ready=pipeline_ok,
        active_cases_in_memory=store.get_case_count(),
        version=settings.api_version,
    )


@router.get("/api/v1/info", response_model=InfoResponse, tags=["System Info"])
def system_info() -> InfoResponse:
    """Returns application metadata, pipeline capabilities, and supported evidence modalities."""
    return InfoResponse()


# -------------------------------------------------------------
# DEMO SCENARIO ENDPOINTS
# -------------------------------------------------------------

@router.get("/api/v1/demo-cases", response_model=List[DemoCaseSummaryResponse], tags=["Demo Cases"], dependencies=[Depends(require_demo_enabled)])
def list_demo_cases(
    store: InMemoryCaseStore = Depends(get_case_store),
) -> List[DemoCaseSummaryResponse]:
    """Lists pre-packaged benchmark demo scenarios for one-click UI evaluation."""
    cases = store.list_demo_cases()
    summaries: List[DemoCaseSummaryResponse] = []
    for c in cases:
        ev_modalities = [e.get("modality", "OTHER") for e in c.get("evidence", [])]
        summaries.append(DemoCaseSummaryResponse(
            case_id=c["case_id"],
            title=c["case_id"].replace("DAY10-", "").replace("-", " ").title(),
            description=c.get("description", ""),
            expected_status=c.get("expected_status", "UNKNOWN"),
            evidence_modalities=list(set(ev_modalities)),
        ))
    return summaries


@router.post("/api/v1/demo-cases/{case_id}/run", response_model=CaseResponse, tags=["Demo Cases"], dependencies=[Depends(require_demo_enabled)])
def run_demo_case(
    case_id: str,
    service: CaseProcessingService = Depends(get_case_service),
    store: InMemoryCaseStore = Depends(get_case_store),
) -> CaseResponse:
    """Executes a pre-packaged demo case directly through the 8-stage pipeline."""
    case_dict = store.get_demo_case_dict(case_id)
    if not case_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo case '{case_id}' not found.",
        )

    result = service.process_benchmark_case(case_dict)
    store.save_case(result)
    return serialize_case_result(result, service.pipeline.provenance_tracker)


# -------------------------------------------------------------
# TRACK 04 BENCHMARK BATCH RECONCILIATION ENDPOINTS
# -------------------------------------------------------------

@router.post("/api/v1/benchmark/run", response_model=BenchmarkRunResponse, tags=["Track 04 Benchmark"], dependencies=[Depends(require_demo_enabled)])
def run_benchmark_batch(
    service: CaseProcessingService = Depends(get_case_service),
) -> BenchmarkRunResponse:
    """Executes the full 96-case ground-truth benchmark through the deterministic pipeline.

    Computes real-time measured match/resolution rates, status distribution, and honest
    exception breakdown across the synthetic batch without modifying persistent state.
    """
    from data.benchmark.loader import load_benchmark_cases
    benchmark_cases = load_benchmark_cases()

    status_counts: Dict[str, int] = {}
    exception_counts: Dict[str, int] = {}
    category_stats: Dict[str, Dict[str, Any]] = {}

    total_evidence = 0
    total_claims = 0
    total_transactions = 0
    total_claimed = 0.0
    total_reconciled = 0.0
    total_outstanding = 0.0
    case_summaries: List[BenchmarkCaseSummary] = []

    start_time = time.perf_counter()

    for bc in benchmark_cases:
        total_evidence += len(bc.evidence)
        total_claims += len(bc.claims)
        total_transactions += len(bc.transactions)

        case_in = CaseInput(
            case_id=bc.case_id,
            evidence_items=bc.evidence,
            transactions=bc.transactions,
            entities=[bc.entity] if bc.entity else [],
            metadata={"precomputed_claims": [cl.model_dump() for cl in bc.claims]} if bc.claims else {},
        )
        res = service.process_case(case_in)

        st = res.status
        status_counts[st] = status_counts.get(st, 0) + 1

        fin = res.financial_summary
        claimed = fin.get("claimed_amount") or 0.0
        matched = fin.get("matched_amount") or 0.0
        outstanding = fin.get("outstanding_amount") or 0.0

        total_claimed += claimed
        total_reconciled += matched
        total_outstanding += outstanding

        disc_types: List[str] = []
        if res.report and res.report.contradiction_summary:
            for c in res.report.contradiction_summary:
                dtype = c.discrepancy_type
                disc_types.append(dtype)
                exception_counts[dtype] = exception_counts.get(dtype, 0) + 1

        cat = bc.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "confirmed": 0, "exceptions": 0, "claimed": 0.0, "matched": 0.0}
        category_stats[cat]["total"] += 1
        category_stats[cat]["claimed"] += claimed
        category_stats[cat]["matched"] += matched
        if st == "CONFIRMED":
            category_stats[cat]["confirmed"] += 1
        else:
            category_stats[cat]["exceptions"] += 1

        review_req = res.status in ("CONTRADICTED", "AMBIGUOUS", "UNVERIFIABLE", "UNMATCHED")

        case_summaries.append(BenchmarkCaseSummary(
            case_id=bc.case_id,
            category=bc.category,
            scenario_title=bc.scenario_title,
            status=st,
            confidence=res.confidence_score,
            claimed_amount=claimed,
            matched_amount=matched,
            outstanding_amount=outstanding,
            discrepancy_count=len(disc_types),
            discrepancy_types=disc_types,
            human_review_required=review_req,
            duration_ms=res.total_execution_time_ms,
        ))

    total_time_ms = (time.perf_counter() - start_time) * 1000.0
    avg_latency_ms = total_time_ms / len(benchmark_cases) if benchmark_cases else 0.0
    match_rate = (total_reconciled / total_claimed * 100.0) if total_claimed > 0.0 else 0.0

    return BenchmarkRunResponse(
        total_cases=len(benchmark_cases),
        total_evidence_items=total_evidence,
        total_claims=total_claims,
        total_transactions=total_transactions,
        total_claimed_value=round(total_claimed, 2),
        total_reconciled_value=round(total_reconciled, 2),
        total_outstanding_value=round(total_outstanding, 2),
        monetary_match_rate=round(match_rate, 2),
        status_distribution=status_counts,
        exception_breakdown=exception_counts,
        category_breakdown=category_stats,
        total_processing_time_ms=round(total_time_ms, 2),
        average_latency_ms=round(avg_latency_ms, 2),
        cases=case_summaries,
    )


# -------------------------------------------------------------
# CASE PROCESSING ENDPOINTS
# -------------------------------------------------------------

@router.post("/api/v1/cases", response_model=CaseResponse, tags=["Cases"])
def submit_case(
    payload: CaseCreateRequest,
    service: CaseProcessingService = Depends(get_case_service),
    store: InMemoryCaseStore = Depends(get_case_store),
) -> CaseResponse:
    """Processes a fully structured financial case through the 8-stage pipeline."""
    case_in = CaseInput(
        case_id=payload.case_id,
        evidence_items=payload.evidence_items,
        raw_file_paths=payload.raw_file_paths,
        raw_text_messages=payload.raw_text_messages,
        transactions=payload.transactions,
        entities=payload.entities,
        metadata=payload.metadata,
    )

    # Security bounds check
    SecurityValidator.validate_case_bounds(case_in)

    result = service.process_case(case_in)
    store.save_case(result)
    return serialize_case_result(result, service.pipeline.provenance_tracker)


@router.post("/api/v1/cases/text", response_model=CaseResponse, tags=["Cases"])
def submit_text_evidence(
    payload: TextEvidenceRequest,
    service: CaseProcessingService = Depends(get_case_service),
    store: InMemoryCaseStore = Depends(get_case_store),
) -> CaseResponse:
    """Ingests and reconstructs financial truth from raw text, WhatsApp, or SMS exports."""
    settings = get_settings()
    SecurityValidator.validate_text_length(payload.text, settings.max_text_length)

    cid = payload.case_id or f"TXT-CASE-{uuid.uuid4().hex[:8]}"
    case_in = CaseInput(
        case_id=cid,
        raw_text_messages=[{
            "text": payload.text,
            "source_name": SecurityValidator.sanitize_filename(payload.source_name or "chat_export.txt"),
        }],
    )

    result = service.process_case(case_in)
    store.save_case(result)
    return serialize_case_result(result, service.pipeline.provenance_tracker)


@router.post("/api/v1/cases/files", response_model=CaseResponse, tags=["Cases"])
async def submit_files_evidence(
    files: List[UploadFile] = File(...),
    case_id: Optional[str] = None,
    service: CaseProcessingService = Depends(get_case_service),
    store: InMemoryCaseStore = Depends(get_case_store),
) -> CaseResponse:
    """Accepts multiple uploaded evidence files (PDF, CSV, Images, Text) with security checks."""
    settings = get_settings()

    if len(files) > settings.max_files_per_case:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exceeded maximum allowed files per upload ({settings.max_files_per_case}). Received {len(files)} files.",
        )

    cid = case_id or f"UPLOAD-CASE-{uuid.uuid4().hex[:8]}"
    temp_dir = tempfile.mkdtemp(prefix="verity_upload_")
    saved_paths: List[str] = []

    try:
        for file in files:
            orig_name = file.filename or f"evidence_{uuid.uuid4().hex[:6]}"
            sanitized_name = SecurityValidator.sanitize_filename(orig_name)

            # Extension validation
            SecurityValidator.validate_file_extension(sanitized_name)

            # Content-type validation
            SecurityValidator.validate_content_type(file.content_type, sanitized_name)

            file_dest = Path(temp_dir) / sanitized_name
            content = await file.read()

            # Size validation
            SecurityValidator.validate_file_size(len(content), settings.max_upload_bytes, sanitized_name)

            with open(file_dest, "wb") as buffer:
                buffer.write(content)
            saved_paths.append(str(file_dest))

        case_in = CaseInput(
            case_id=cid,
            raw_file_paths=saved_paths,
        )

        result = service.process_case(case_in)
        store.save_case(result)
        return serialize_case_result(result, service.pipeline.provenance_tracker)
    finally:
        # Cleanup temporary files
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


# -------------------------------------------------------------
# CASE RETRIEVAL & INSPECTION ENDPOINTS
# -------------------------------------------------------------

@router.get("/api/v1/cases/{case_id}", response_model=CaseResponse, tags=["Cases"])
def get_case(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
    service: CaseProcessingService = Depends(get_case_service),
) -> CaseResponse:
    """Retrieves an existing case result from memory."""
    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    return serialize_case_result(result, service.pipeline.provenance_tracker)


@router.get("/api/v1/cases/{case_id}/report", tags=["Reporting"])
def get_case_report(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
) -> Dict[str, Any]:
    """Returns the structured FinancialTruthReport JSON for a case."""
    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    if not result.report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No FinancialTruthReport generated for case '{case_id}'.",
        )
    return result.report.model_dump()


@router.get("/api/v1/cases/{case_id}/provenance", response_model=ProvenanceGraphResponse, tags=["Provenance"])
def get_case_provenance(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
    service: CaseProcessingService = Depends(get_case_service),
) -> ProvenanceGraphResponse:
    """Returns the structured DAG trace linking truth back to root evidence."""
    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    return serialize_provenance_graph(case_id, service.pipeline.provenance_tracker)


# -------------------------------------------------------------
# AI FINANCE CONTROLLER DECISION INTELLIGENCE ENDPOINTS
# -------------------------------------------------------------

@router.get("/api/v1/cases/{case_id}/controller", tags=["Finance Controller"])
def get_case_controller_decision(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns the structured ControllerDecision for a reconciled case."""
    from backend.api.dependencies import get_controller_service
    controller_svc = get_controller_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    return controller_svc.analyze_case(result)


@router.get("/api/v1/cases/{case_id}/controller/brief", tags=["Finance Controller"])
def get_case_controller_brief(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns the executive ControllerBrief synthesizing risks, financial metrics, and recommendations."""
    from backend.api.dependencies import get_controller_service
    controller_svc = get_controller_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    return controller_svc.build_brief(result)


@router.post("/api/v1/cases/{case_id}/controller/explain", tags=["Finance Controller"])
def explain_case_query(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Answers natural-language controller queries using strictly deterministic grounding facts."""
    from backend.api.dependencies import get_controller_service
    controller_svc = get_controller_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    question = payload.get("question", "Why is human review required for this case?")
    return controller_svc.explain_query(result, question)


# -------------------------------------------------------------
# HUMAN REVIEW & AUDIT WORKFLOW ENDPOINTS (DAY 14)
# -------------------------------------------------------------

@router.get("/api/v1/cases/{case_id}/review", tags=["Human Review"])
def get_or_create_case_review(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Retrieves or initializes the human review record for a financial case."""
    from backend.api.dependencies import get_controller_service, get_review_service
    review_svc = get_review_service()
    controller_svc = get_controller_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    return review_svc.create_or_get_review(result, decision)


@router.post("/api/v1/cases/{case_id}/review/start", tags=["Human Review"])
def start_case_review(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Transitions review to IN_PROGRESS state."""
    from backend.api.dependencies import get_review_service
    from backend.review.workflow import InvalidStateTransitionError
    from backend.review.service import CaseReviewNotFoundError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    reviewer_id = payload.get("reviewer_id", "controller_1")
    reviewer_name = payload.get("reviewer_name", "Finance Controller")
    try:
        return review_svc.start_review(case_id, reviewer_id=reviewer_id, reviewer_name=reviewer_name)
    except (InvalidStateTransitionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/note", tags=["Human Review"])
def add_case_review_note(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Appends an immutable timestamped note to the review."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError, ReviewClosedError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    content = payload.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note content cannot be empty.")
    reviewer_id = payload.get("reviewer_id", "controller_1")
    reviewer_name = payload.get("reviewer_name", "Finance Controller")
    try:
        return review_svc.add_note(case_id, reviewer_id=reviewer_id, reviewer_name=reviewer_name, content=content)
    except ReviewClosedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/evidence/{evidence_id}", tags=["Human Review"])
def mark_evidence_as_reviewed(
    case_id: str,
    evidence_id: str,
    payload: Dict[str, Any] = None,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Records that an individual evidence item was inspected."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError, InvalidReferenceError, ReviewClosedError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    valid_ev_ids = []
    if result.report and result.report.evidence_summary:
        valid_ev_ids = [e.evidence_id for e in result.report.evidence_summary]
    elif result.reconciliation:
        valid_ev_ids = list(result.reconciliation.evidence_ids)
    payload = payload or {}
    reviewer_id = payload.get("reviewer_id", "controller_1")
    reviewer_name = payload.get("reviewer_name", "Finance Controller")
    notes = payload.get("notes")
    try:
        return review_svc.mark_evidence_reviewed(
            case_id=case_id,
            evidence_id=evidence_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            notes=notes,
            valid_evidence_ids=valid_ev_ids,
        )
    except (InvalidReferenceError, ReviewClosedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/action", tags=["Human Review"])
def create_case_review_action(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Creates a new investigation task."""
    from backend.api.dependencies import get_review_service
    from backend.review.models import ReviewActionType
    from backend.review.service import CaseReviewNotFoundError, ReviewClosedError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    title = payload.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action title cannot be empty.")
    act_type_str = payload.get("action_type", "REVIEW_EVIDENCE")
    try:
        act_type = ReviewActionType(act_type_str)
    except ValueError:
        act_type = ReviewActionType.REVIEW_EVIDENCE

    try:
        return review_svc.create_action(
            case_id=case_id,
            action_type=act_type,
            title=title,
            description=payload.get("description", ""),
            priority=payload.get("priority", 1),
            supporting_ids=payload.get("supporting_ids", []),
            reviewer_id=payload.get("reviewer_id", "controller_1"),
        )
    except ReviewClosedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/action/{action_id}/complete", tags=["Human Review"])
def complete_case_review_action(
    case_id: str,
    action_id: str,
    payload: Dict[str, Any] = None,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Marks an investigation action task as completed."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError, InvalidReferenceError, ReviewClosedError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    payload = payload or {}
    try:
        return review_svc.complete_action(
            case_id=case_id,
            action_id=action_id,
            reviewer_id=payload.get("reviewer_id", "controller_1"),
            notes=payload.get("notes"),
        )
    except (InvalidReferenceError, ReviewClosedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/decision", tags=["Human Review"])
def record_case_review_decision(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Records human reviewer decision (never mutates deterministic reconciliation truth)."""
    from backend.api.dependencies import get_review_service
    from backend.review.models import ReviewDecision
    from backend.review.service import CaseReviewNotFoundError, ReviewClosedError
    from backend.review.workflow import InvalidStateTransitionError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    dec_str = payload.get("decision")
    try:
        dec = ReviewDecision(dec_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid review decision '{dec_str}'.")

    try:
        return review_svc.record_decision(
            case_id=case_id,
            decision=dec,
            reviewer_id=payload.get("reviewer_id", "controller_1"),
            reviewer_name=payload.get("reviewer_name", "Finance Controller"),
            notes=payload.get("notes"),
        )
    except (InvalidStateTransitionError, ReviewClosedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/escalate", tags=["Human Review"])
def escalate_case_review(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Escalates case to senior controller."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError
    from backend.review.workflow import InvalidStateTransitionError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    reason = payload.get("reason", "").strip()
    if not reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escalation reason cannot be empty.")

    try:
        return review_svc.escalate(
            case_id=case_id,
            reason=reason,
            reviewer_id=payload.get("reviewer_id", "controller_1"),
            reviewer_name=payload.get("reviewer_name", "Finance Controller"),
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/resolve", tags=["Human Review"])
def resolve_case_review(
    case_id: str,
    payload: Dict[str, Any] = None,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Marks review investigation as RESOLVED."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError
    from backend.review.workflow import InvalidStateTransitionError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    payload = payload or {}
    try:
        return review_svc.resolve(
            case_id=case_id,
            reviewer_id=payload.get("reviewer_id", "controller_1"),
            reviewer_name=payload.get("reviewer_name", "Finance Controller"),
            notes=payload.get("notes"),
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.post("/api/v1/cases/{case_id}/review/close", tags=["Human Review"])
def close_case_review(
    case_id: str,
    payload: Dict[str, Any] = None,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Permanently seals and closes review record."""
    from backend.api.dependencies import get_review_service
    from backend.review.service import CaseReviewNotFoundError
    from backend.review.workflow import InvalidStateTransitionError
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    payload = payload or {}
    try:
        return review_svc.close(
            case_id=case_id,
            reviewer_id=payload.get("reviewer_id", "controller_1"),
            reviewer_name=payload.get("reviewer_name", "Finance Controller"),
            notes=payload.get("notes"),
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CaseReviewNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Review for case '{case_id}' not found.")


@router.get("/api/v1/cases/{case_id}/review/audit", tags=["Human Review"])
def get_case_review_audit_log(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns the immutable list of audit events for a case review."""
    from backend.api.dependencies import get_review_service
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    return review_svc.get_audit_log(case_id)


@router.get("/api/v1/cases/{case_id}/review/audit/verify", tags=["Human Review"])
def verify_case_review_audit_chain(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Cryptographically verifies that the audit hash-chain is unbroken and un-tampered."""
    from backend.api.dependencies import get_review_service
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    is_valid, details = review_svc.validate_audit_chain(case_id)
    events = review_svc.get_audit_log(case_id)
    return {
        "case_id": case_id,
        "is_valid": is_valid,
        "event_count": len(events),
        "root_hash": events[0].current_state_hash if events else None,
        "latest_hash": events[-1].current_state_hash if events else None,
        "details": details,
    }


@router.get("/api/v1/cases/{case_id}/review/summary", tags=["Human Review"])
def get_case_review_summary(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns a synthesized summary distinguishing deterministic truth from human decisions."""
    from backend.api.dependencies import get_controller_service, get_review_service
    review_svc = get_review_service()
    controller_svc = get_controller_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review_svc.create_or_get_review(result, decision)
    return review_svc.get_summary(
        case_id=case_id,
        deterministic_status=result.status,
        controller_risk_level=decision.risk_level.value,
        requires_review=decision.requires_human_review,
    )


# -------------------------------------------------------------
# FINANCIAL CASE PORTFOLIO & OPERATIONS INTELLIGENCE (DAY 15)
# -------------------------------------------------------------

def _sync_portfolio_from_store(store: InMemoryCaseStore, portfolio_svc, controller_svc, review_svc) -> None:
    """Helper to ensure all session store cases are indexed in the portfolio."""
    for c in store.list_cases():
        decision = controller_svc.analyze_case(c)
        review = review_svc.get_review(c.case_id)
        portfolio_svc.register_case(c, decision, review)


@router.get("/api/v1/portfolio", tags=["Case Portfolio"])
def get_portfolio_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    risk_level: Optional[str] = None,
    reviewer_id: Optional[str] = None,
    deterministic_status: Optional[str] = None,
    human_review_status: Optional[str] = None,
    sla_status: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    entity_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "priority",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns a filtered, sorted, and paginated view of the financial case portfolio."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.models import (
        PortfolioCaseStatus,
        PortfolioFilter,
        PortfolioPriority,
        PortfolioSort,
        PortfolioSortField,
        SLAStatus,
        SortOrder,
    )

    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)

    filters = PortfolioFilter(
        status=PortfolioCaseStatus(status) if status else None,
        priority=PortfolioPriority(priority) if priority else None,
        risk_level=risk_level,
        reviewer_id=reviewer_id,
        deterministic_status=deterministic_status,
        human_review_status=human_review_status,
        sla_status=SLAStatus(sla_status) if sla_status else None,
        min_amount=min_amount,
        max_amount=max_amount,
        entity_id=entity_id,
        search=search,
    )

    try:
        sort_field = PortfolioSortField(sort_by)
    except ValueError:
        sort_field = PortfolioSortField.PRIORITY

    try:
        s_order = SortOrder(sort_order.lower())
    except ValueError:
        s_order = SortOrder.DESC

    sort = PortfolioSort(field=sort_field, order=s_order)
    return portfolio_svc.query_cases(filters=filters, sort=sort, page=page, page_size=page_size)


@router.get("/api/v1/portfolio/summary", tags=["Case Portfolio"])
def get_portfolio_summary(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns executive portfolio-wide health and operational status metrics."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_summary()


@router.get("/api/v1/portfolio/exposure", tags=["Case Portfolio"])
def get_portfolio_exposure(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns monetary exposure calculations across risks and statuses with zero double-counting."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_exposure()


@router.get("/api/v1/portfolio/workload", tags=["Case Portfolio"])
def get_portfolio_workload(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns reviewer workload allocations and capacity alerts."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_workload()


@router.get("/api/v1/portfolio/cases/{case_id}", tags=["Case Portfolio"])
def get_portfolio_case_detail(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Retrieves operational portfolio details for a single financial case."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )

    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    return portfolio_svc.register_case(result, decision, review)


@router.get("/api/v1/portfolio/cases/{case_id}/sla", tags=["Case Portfolio"])
def get_portfolio_case_sla(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns detailed SLA deadline, elapsed time, and status for a case."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.service import PortfolioCaseNotFoundError
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    portfolio_svc.register_case(result, decision, review)

    try:
        sla_stat, due_at, elapsed_h, remain_h = portfolio_svc.calculate_sla(case_id)
        return {
            "case_id": case_id,
            "sla_status": sla_stat.value,
            "due_at": due_at.isoformat(),
            "elapsed_hours": round(elapsed_h, 2),
            "remaining_hours": round(remain_h, 2),
        }
    except PortfolioCaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")


@router.get("/api/v1/portfolio/cases/{case_id}/priority", tags=["Case Portfolio"])
def get_portfolio_case_priority_score(
    case_id: str,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns deterministic priority score and rationale breakdown for a case."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.service import PortfolioCaseNotFoundError
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    portfolio_svc.register_case(result, decision, review)

    try:
        return portfolio_svc.prioritize_case(case_id)
    except PortfolioCaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")


@router.post("/api/v1/portfolio/cases/{case_id}/assign", tags=["Case Portfolio"])
def assign_portfolio_case(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Assigns an operational reviewer to a case."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.service import PortfolioCaseNotFoundError
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    portfolio_svc.register_case(result, decision, review)

    reviewer_id = payload.get("reviewer_id", "").strip()
    if not reviewer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reviewer ID cannot be empty.")
    reviewer_name = payload.get("reviewer_name")
    assigned_by = payload.get("assigned_by", "controller_admin")

    try:
        return portfolio_svc.assign_case(
            case_id=case_id,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            assigned_by=assigned_by,
        )
    except PortfolioCaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")


@router.post("/api/v1/portfolio/cases/{case_id}/reassign", tags=["Case Portfolio"])
def reassign_portfolio_case(
    case_id: str,
    payload: Dict[str, Any],
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Reassigns a case to a new reviewer."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.service import PortfolioCaseNotFoundError
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    portfolio_svc.register_case(result, decision, review)

    new_reviewer_id = payload.get("new_reviewer_id", "").strip()
    if not new_reviewer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New reviewer ID cannot be empty.")
    new_reviewer_name = payload.get("new_reviewer_name")
    reassigned_by = payload.get("reassigned_by", "controller_admin")
    reason = payload.get("reason")

    try:
        return portfolio_svc.reassign_case(
            case_id=case_id,
            new_reviewer_id=new_reviewer_id,
            new_reviewer_name=new_reviewer_name,
            reassigned_by=reassigned_by,
            reason=reason,
        )
    except PortfolioCaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")


@router.post("/api/v1/portfolio/cases/{case_id}/unassign", tags=["Case Portfolio"])
def unassign_portfolio_case(
    case_id: str,
    payload: Dict[str, Any] = None,
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Removes active reviewer assignment from a case."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    from backend.portfolio.service import PortfolioCaseNotFoundError
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    result = store.get_case(case_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found in demo session store.",
        )
    decision = controller_svc.analyze_case(result)
    review = review_svc.get_review(case_id)
    portfolio_svc.register_case(result, decision, review)

    payload = payload or {}
    unassigned_by = payload.get("unassigned_by", "controller_admin")
    reason = payload.get("reason")

    try:
        return portfolio_svc.unassign_case(
            case_id=case_id,
            unassigned_by=unassigned_by,
            reason=reason,
        )
    except PortfolioCaseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{case_id}' not found.")


@router.get("/api/v1/portfolio/review-queue", tags=["Case Portfolio"])
def get_portfolio_review_queue(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns prioritized queue of cases requiring human review."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_review_queue()


@router.get("/api/v1/portfolio/overdue", tags=["Case Portfolio"])
def get_portfolio_overdue_queue(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns queue of cases currently violating operational SLA deadlines."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_overdue_queue()


@router.get("/api/v1/portfolio/high-risk", tags=["Case Portfolio"])
def get_portfolio_high_risk_queue(
    store: InMemoryCaseStore = Depends(get_case_store),
):
    """Returns queue of cases categorized as CRITICAL or HIGH risk."""
    from backend.api.dependencies import (
        get_controller_service,
        get_portfolio_service,
        get_review_service,
    )
    portfolio_svc = get_portfolio_service()
    controller_svc = get_controller_service()
    review_svc = get_review_service()

    _sync_portfolio_from_store(store, portfolio_svc, controller_svc, review_svc)
    return portfolio_svc.get_high_risk_queue()


# -------------------------------------------------------------
# 8. PERSISTENT STORAGE & AUDIT INFRASTRUCTURE (DAY 16)
# -------------------------------------------------------------
@router.get("/api/v1/storage/health", tags=["Storage & Infrastructure"])
def get_storage_health():
    """Returns live database engine connectivity and storage diagnostics."""
    from backend.api.dependencies import get_storage_service
    storage = get_storage_service()
    return storage.check_health()


@router.get("/api/v1/storage/stats", tags=["Storage & Infrastructure"])
def get_storage_stats():
    """Returns persistent table counts and storage volume statistics."""
    from backend.api.dependencies import get_storage_service
    storage = get_storage_service()
    return {
        "status": "HEALTHY",
        "tables": storage.get_storage_stats(),
    }


@router.get("/api/v1/cases/{case_id}/persistence", tags=["Storage & Infrastructure"])
def get_case_persistence_status(case_id: str):
    """Checks persistent presence of all artifacts for a given case."""
    from backend.api.dependencies import get_storage_service
    storage = get_storage_service()
    case_res = storage.get_case_result(case_id)
    review_rec = storage.get_review(case_id)
    port_state = storage.get_portfolio_state(case_id)
    audit_events = storage.audit_store.get_events(case_id)

    if not case_res and not review_rec and not port_state and not audit_events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No persistent records found for case '{case_id}'",
        )

    return {
        "case_id": case_id,
        "is_persisted": case_res is not None,
        "deterministic_status": case_res.status if case_res else None,
        "has_reconciliation": case_res.reconciliation is not None if case_res else False,
        "has_truth_report": case_res.report is not None if case_res else False,
        "has_review_record": review_rec is not None,
        "has_portfolio_state": port_state is not None,
        "audit_event_count": len(audit_events),
    }


@router.get("/api/v1/cases/{case_id}/audit/integrity", tags=["Storage & Infrastructure"])
def verify_case_audit_integrity(case_id: str):
    """Verifies cryptographic SHA-256 hash-chain integrity for a persisted case."""
    from backend.api.dependencies import get_storage_service
    storage = get_storage_service()
    is_valid, errors = storage.audit_store.verify_chain(case_id)
    events = storage.audit_store.get_events(case_id)

    return {
        "case_id": case_id,
        "is_valid": is_valid,
        "total_events": len(events),
        "errors": errors,
        "latest_state_hash": events[-1].current_state_hash if events else None,
    }


# -------------------------------------------------------------
# CROSS-CASE INTELLIGENCE & COUNTERPARTY MEMORY (Day 18)
# -------------------------------------------------------------

@router.get("/api/v1/entities/{entity_name_or_id}/history", tags=["Cross-Case Intelligence"])
def get_entity_history(
    entity_name_or_id: str,
    exclude_case_id: Optional[str] = None,
):
    """Fetches lifetime counterparty history, multi-case volume, and contradiction frequency."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    history = cross_svc.get_counterparty_history(entity_name_or_id, exclude_case_id=exclude_case_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No counterparty history found for '{entity_name_or_id}'",
        )
    return history.model_dump()


@router.get("/api/v1/entities/{entity_name_or_id}/exposure", tags=["Cross-Case Intelligence"])
def get_entity_exposure_summary(
    entity_name_or_id: str,
):
    """Fetches aggregate lifetime exposure breakdown for a counterparty."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    history = cross_svc.get_counterparty_history(entity_name_or_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No exposure data found for counterparty '{entity_name_or_id}'",
        )
    return {
        "entity_id": history.entity_id,
        "canonical_name": history.canonical_name,
        "case_count": history.case_count,
        "total_exposure": history.total_exposure,
        "disputed_exposure": history.disputed_exposure,
        "unresolved_exposure": history.unresolved_exposure,
        "contradiction_count": history.contradiction_count,
    }


@router.get("/api/v1/references/{reference_id}/history", tags=["Cross-Case Intelligence"])
def get_reference_history_endpoint(
    reference_id: str,
    current_case_id: Optional[str] = None,
):
    """Checks reference/UTR across all historical transactions and claims for duplicate reuse."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    correlation = cross_svc.get_reference_history(reference_id, current_case_id=current_case_id)
    return correlation.model_dump()


@router.get("/api/v1/cases/{case_id}/correlations", tags=["Cross-Case Intelligence"])
def get_case_correlations_endpoint(case_id: str):
    """Discovers deterministic relationships between a case and historical cases."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    correlations = cross_svc.get_case_correlations(case_id)
    return [c.model_dump() for c in correlations]


@router.get("/api/v1/cases/{case_id}/historical-signals", tags=["Cross-Case Intelligence"])
def get_case_historical_signals_endpoint(case_id: str):
    """Extracts explainable, deterministic historical risk signals for a case."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    signals = cross_svc.get_historical_risk_signals(case_id)
    return [s.model_dump() for s in signals]


@router.get("/api/v1/cases/{case_id}/intelligence-profile", tags=["Cross-Case Intelligence"])
def get_case_intelligence_profile_endpoint(case_id: str):
    """Fetches the complete institutional memory and cross-case intelligence dossier for a case."""
    from backend.api.dependencies import get_cross_case_service
    cross_svc = get_cross_case_service()
    profile = cross_svc.build_case_intelligence_profile(case_id)
    return profile.model_dump()


# =============================================================
# DAY 19: PROACTIVE CONTROLLER ACTIONS & REMEDIATION ENDPOINTS
# =============================================================

@router.post("/api/v1/cases/{case_id}/actions/propose", tags=["Proactive Remediation"])
def propose_remediation_action_endpoint(
    case_id: str,
    payload: Dict[str, Any] = None,
):
    """Proposes a fact-grounded remediation action (Dispute Notice, Payment Follow-up, Missing Evidence Request, or Draft Journal Voucher)."""
    from backend.api.dependencies import get_remediation_service
    from backend.controller.remediation.models import NoticeChannel, RemediationActionType
    svc = get_remediation_service()
    payload = payload or {}
    action_type = payload.get("action_type", "VENDOR_DISPUTE_NOTICE")
    channel_str = payload.get("channel", "EMAIL")
    channel = NoticeChannel(channel_str) if channel_str in NoticeChannel.__members__ else NoticeChannel.EMAIL
    recipient_contact = payload.get("recipient_contact")

    try:
        if action_type == RemediationActionType.VENDOR_DISPUTE_NOTICE.value or action_type == "VENDOR_DISPUTE_NOTICE":
            action = svc.propose_dispute_notice(case_id, channel=channel, recipient_contact=recipient_contact)
        elif action_type == RemediationActionType.PAYMENT_FOLLOWUP_DRAFT.value or action_type == "PAYMENT_FOLLOWUP_DRAFT":
            action = svc.propose_payment_followup(case_id, channel=channel, recipient_contact=recipient_contact)
        elif action_type == RemediationActionType.MISSING_EVIDENCE_REQUEST.value or action_type == "MISSING_EVIDENCE_REQUEST":
            action = svc.propose_missing_evidence_request(case_id, channel=channel, recipient_contact=recipient_contact)
        elif action_type == RemediationActionType.DRAFT_JOURNAL_VOUCHER.value or action_type == "DRAFT_JOURNAL_VOUCHER":
            action = svc.propose_journal_voucher_action(case_id, custom_coa_mapping=payload.get("custom_coa_mapping"))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported action type: {action_type}")
        return action.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/v1/cases/{case_id}/actions", tags=["Proactive Remediation"])
def list_case_remediation_actions_endpoint(case_id: str):
    """Lists all proposed and reviewed remediation actions for a case."""
    from backend.api.dependencies import get_remediation_service
    svc = get_remediation_service()
    actions = svc.list_actions_by_case(case_id)
    return [a.model_dump() for a in actions]


@router.post("/api/v1/cases/{case_id}/actions/{action_id}/approve", tags=["Proactive Remediation"])
def approve_remediation_action_endpoint(
    case_id: str,
    action_id: str,
    payload: Dict[str, Any] = None,
):
    """Explicit human approval of a proposed remediation action."""
    from backend.api.dependencies import get_remediation_service
    svc = get_remediation_service()
    payload = payload or {}
    reviewer_id = payload.get("reviewer_id", "controller_1")
    notes = payload.get("notes")

    try:
        action = svc.approve_action(action_id, reviewer_id=reviewer_id, notes=notes)
        return action.model_dump()
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/api/v1/cases/{case_id}/actions/{action_id}/reject", tags=["Proactive Remediation"])
def reject_remediation_action_endpoint(
    case_id: str,
    action_id: str,
    payload: Dict[str, Any] = None,
):
    """Explicit human rejection of a proposed remediation action."""
    from backend.api.dependencies import get_remediation_service
    svc = get_remediation_service()
    payload = payload or {}
    reviewer_id = payload.get("reviewer_id", "controller_1")
    reason = payload.get("reason", "Controller rejected proposed action")
    notes = payload.get("notes")

    try:
        action = svc.reject_action(action_id, reviewer_id=reviewer_id, rejection_reason=reason, notes=notes)
        return action.model_dump()
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/api/v1/cases/{case_id}/journal-voucher", tags=["Proactive Remediation"])
def get_case_journal_voucher_endpoint(
    case_id: str,
):
    """Constructs and returns a deterministic double-entry Draft Journal Voucher for a case."""
    from backend.api.dependencies import get_remediation_service
    svc = get_remediation_service()
    try:
        voucher = svc.build_draft_journal_voucher(case_id)
        return voucher.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/api/v1/cases/{case_id}/journal-voucher/export", tags=["Proactive Remediation"])
def export_case_journal_voucher_endpoint(
    case_id: str,
    payload: Dict[str, Any] = None,
):
    """Exports the balanced draft journal voucher and records an immutable audit event."""
    from backend.api.dependencies import get_remediation_service
    svc = get_remediation_service()
    payload = payload or {}
    try:
        voucher = svc.build_draft_journal_voucher(case_id, custom_coa_mapping=payload.get("custom_coa_mapping"))
        # Record audit event for journal export
        svc._record_audit_event(
            case_id=case_id,
            event_type="JOURNAL_EXPORTED",
            description=f"Exported Draft Journal Voucher {voucher.voucher_id} (Balanced: INR {voucher.total_debits:,.2f})",
            affected_ids=[voucher.voucher_id],
        )
        return {
            "status": "EXPORTED",
            "voucher": voucher.model_dump(),
            "export_format": payload.get("format", "JSON"),
            "audit_recorded": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
