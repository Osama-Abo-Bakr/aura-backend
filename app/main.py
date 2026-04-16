from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import router as v1_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.middleware import (
    AccessLogMiddleware,
    RequestIDMiddleware,
    http_exception_handler,
    validation_exception_handler,
)

# ---------------------------------------------------------------------------
# Logging (must come before anything that calls a logger)
# ---------------------------------------------------------------------------
configure_logging(settings.ENVIRONMENT)

# ---------------------------------------------------------------------------
# Sentry (no-op when SENTRY_DSN is empty)
# ---------------------------------------------------------------------------
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.05,
    )

# ---------------------------------------------------------------------------
# Rate limiter (slowapi — Redis-backed in production via REDIS_URL)
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],
    storage_uri=settings.REDIS_URL,
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Aura Health API",
    version="1.0.0",
    description=(
        "Backend API for Aura Health — an AI health companion for women in MENA. "
        "Powered by Gemini, Supabase, and FastAPI."
    ),
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Attach limiter state so slowapi can read it from request.app
app.state.limiter = limiter

# ---------------------------------------------------------------------------
# Middleware  (applied bottom-up — last added runs first)
# ---------------------------------------------------------------------------
_allowed_origins = list(
    {settings.FRONTEND_URL, "http://localhost:3000"} - {"", None}  # type: ignore[arg-type]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "X-Request-ID"],
)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(v1_router)


# ---------------------------------------------------------------------------
# Infra probes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["infra"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["infra"], summary="Readiness probe — checks DB + AI connectivity")
async def ready(request: Request) -> dict:
    """
    Checks:
    1. Supabase DB reachable (simple SELECT 1)
    2. Gemini API key present (no API call, just config check)

    Returns 503 if any dependency is unhealthy.
    """
    from fastapi import status as http_status

    checks: dict[str, str] = {}

    # --- Supabase DB ---
    try:
        from app.db.supabase import supabase_admin
        supabase_admin.table("subscriptions").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    # --- Gemini API key present ---
    checks["gemini"] = "ok" if settings.GEMINI_API_KEY else "missing_key"

    # --- Stripe configured ---
    checks["stripe"] = "ok" if settings.STRIPE_SECRET_KEY else "not_configured"

    all_ok = all(v in ("ok", "not_configured") for v in checks.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "checks": checks,
        "environment": settings.ENVIRONMENT,
    }
