"""
Production middleware stack for Aura Health API.

- RequestIDMiddleware  : injects X-Request-ID into every request/response
- StructuredLoggingMiddleware : emits one structured JSON log line per request
- custom_http_exception_handler : normalised error envelope
- custom_validation_exception_handler : 422 with field-level detail
"""

from __future__ import annotations

import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique X-Request-ID to every request.
    Reads the header from the client if provided, otherwise generates a new UUID.
    The same ID is echoed back in the response so clients can correlate logs.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Make it available to the rest of the request lifecycle
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# Structured access-log middleware
# ---------------------------------------------------------------------------


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Emit one structured JSON line per request:
    {method, path, status, duration_ms, request_id}
    """

    _SKIP_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        request_id = getattr(request.state, "request_id", "-")

        log = logger.bind(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        if response.status_code >= 500:
            log.error("request_completed")
        elif response.status_code >= 400:
            log.warning("request_completed")
        else:
            log.info("request_completed")

        return response


# ---------------------------------------------------------------------------
# Custom exception handlers
# ---------------------------------------------------------------------------


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """Normalise HTTPException into {error, message, request_id}."""
    request_id = getattr(request.state, "request_id", None)

    # exc.detail may already be a dict (our API style) or a plain string
    if isinstance(exc.detail, dict):
        body = exc.detail
    else:
        body = {"error": "http_error", "message": str(exc.detail)}

    if request_id:
        body["request_id"] = request_id

    return JSONResponse(status_code=exc.status_code, content=body)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 with structured field-level errors."""
    request_id = getattr(request.state, "request_id", None)

    errors = []
    for e in exc.errors():
        errors.append(
            {
                "field": ".".join(str(p) for p in e["loc"]),
                "message": e["msg"],
                "type": e["type"],
            }
        )

    body: dict = {
        "error": "validation_error",
        "message": "Request body failed validation.",
        "errors": errors,
    }
    if request_id:
        body["request_id"] = request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body,
    )
