"""FastAPI Application factory with security middleware, error handlers, and logging."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.auth import SupabaseAuthMiddleware, supabase_public_config
from backend.api.logging import (
    RequestIDAndLoggingMiddleware,
    get_current_request_id,
    setup_logging,
)
from backend.api.models import ErrorCode, ErrorDetail, ErrorResponse
from backend.api.routes import router
from backend.api.user_routes import router as user_router
from backend.config import Settings, get_settings

logger = logging.getLogger("verity.app")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware attaching standard defensive security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Cache control for dynamic API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        else:
            # Static web app: always revalidate (cheap via ETag) so new deploys show up immediately
            response.headers.setdefault("Cache-Control", "no-cache")
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Creates and configures the FastAPI application instance with security hardening."""
    cfg = settings or get_settings()
    setup_logging(cfg.log_level)

    app = FastAPI(
        title="FinSync — Payment checks against your bank statement",
        description="Rule-based payment reconciliation API: checks invoices, payment messages and screenshots against your bank statement.",
        version=cfg.api_version,
        docs_url="/docs" if cfg.enable_docs else None,
        redoc_url="/redoc" if cfg.enable_docs else None,
    )

    # 1. Attach Request-ID & Structured Logging Middleware
    app.add_middleware(RequestIDAndLoggingMiddleware)

    # 2. Attach Defensive Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Configurable CORS Middleware (No wildcard defaults in production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 4. Supabase auth (outermost) — scopes every API request to the signed-in user's workspace
    app.add_middleware(SupabaseAuthMiddleware)

    @app.get("/api/v1/config", tags=["System Info"])
    def public_config() -> dict:
        """Public client configuration (Supabase URL and anon key are safe to expose)."""
        return supabase_public_config()

    @app.on_event("startup")
    def _startup() -> None:
        from backend import cloud_sync
        cloud_sync.ensure_bucket()

    @app.on_event("shutdown")
    def _shutdown() -> None:
        from backend import cloud_sync
        cloud_sync.flush_all()

    # -------------------------------------------------------------
    # STANDARDIZED API ERROR HANDLERS
    # -------------------------------------------------------------

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handles HTTPExceptions with standardized ErrorResponse format."""
        rid = get_current_request_id()
        
        # Map HTTP status codes to stable error codes
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            code = ErrorCode.CASE_NOT_FOUND
        elif exc.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            code = ErrorCode.FILE_TOO_LARGE
        elif exc.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE:
            code = ErrorCode.UNSUPPORTED_MEDIA
        elif exc.status_code == status.HTTP_400_BAD_REQUEST:
            code = ErrorCode.INVALID_INPUT
        elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            code = ErrorCode.RESOURCE_LIMIT
        else:
            code = ErrorCode.PROCESSING_ERROR

        error_detail = ErrorDetail(code=code, message=str(exc.detail), request_id=rid)
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=error_detail).model_dump(),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handles Pydantic validation errors safely without exposing internal tracebacks."""
        rid = get_current_request_id()
        error_msgs = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            error_msgs.append(f"Field '{loc}': {msg}")

        message = "; ".join(error_msgs) if error_msgs else "Invalid request payload format."
        error_detail = ErrorDetail(code=ErrorCode.INVALID_INPUT, message=message, request_id=rid)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(error=error_detail).model_dump(),
            headers={"X-Request-ID": rid},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catches unhandled exceptions, logs internal traceback, and returns safe response."""
        rid = get_current_request_id()
        logger.exception(f"Unhandled exception on {request.method} {request.url.path} [request_id={rid}]: {exc}")
        
        # Do NOT leak internal traceback to API client
        error_detail = ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="An internal server error occurred while processing the financial case. Reference the request ID for diagnostics.",
            request_id=rid,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(error=error_detail).model_dump(),
            headers={"X-Request-ID": rid},
        )

    # 5. Include API Router
    app.include_router(router)
    app.include_router(user_router)

    # 6. Mount Frontend Static Assets if directory exists
    frontend_dir = Path("frontend")
    if frontend_dir.exists() and (frontend_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app


app = create_app()
