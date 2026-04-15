import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as v1_router
from app.core.config import settings

# ---------------------------------------------------------------------------
# Sentry (no-op when SENTRY_DSN is empty)
# ---------------------------------------------------------------------------
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        traces_sample_rate=0.2,
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
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Middleware
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
    expose_headers=["Content-Type"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(v1_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["infra"], summary="Liveness probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}
