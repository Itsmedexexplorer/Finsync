"""Structured logging and Request-ID propagation for the VERITY API."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Context variable to hold request_id across async call frames
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger("verity.api")


def setup_logging(log_level: str = "INFO") -> None:
    """Configures application-wide structured logging format."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(level)


def get_current_request_id() -> str:
    """Retrieves the current request ID from context or generates a new one."""
    rid = request_id_var.get()
    if not rid:
        rid = f"req-{uuid.uuid4().hex[:12]}"
        request_id_var.set(rid)
    return rid


class RequestIDAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for Request-ID generation, propagation, and structured request logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        # 1. Extract or generate Request ID
        client_req_id = request.headers.get("X-Request-ID")
        req_id = client_req_id if client_req_id else f"req-{uuid.uuid4().hex[:12]}"
        request_id_var.set(req_id)

        # 2. Log request start
        client_ip = request.client.host if request.client else "unknown"
        logger.info(
            f"[REQ_START] {request.method} {request.url.path} "
            f"request_id={req_id} client={client_ip}"
        )

        try:
            # 3. Process request
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"[REQ_EXCEPTION] {request.method} {request.url.path} "
                f"request_id={req_id} duration_ms={duration_ms:.2f} error={str(exc)}"
            )
            raise exc

        # 4. Attach X-Request-ID to response headers
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = req_id

        # 5. Log request complete
        logger.info(
            f"[REQ_COMPLETE] {request.method} {request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms:.2f} request_id={req_id}"
        )

        return response
