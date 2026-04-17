# Aura Health API

Backend API for **Aura Health** — an AI health companion for women in MENA. Powered by FastAPI, Supabase, Gemini, and Stripe.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
  - [Auth](#auth)
  - [Profile & Me](#profile--me)
  - [Chat](#chat)
  - [Analysis](#analysis)
  - [Health Log](#health-log)
  - [Subscriptions](#subscriptions)
  - [Tickets](#tickets)
  - [Wellness](#wellness)
  - [Infrastructure](#infrastructure)
- [Authentication](#authentication)
- [Rate Limiting & Quotas](#rate-limiting--quotas)
- [Background Tasks](#background-tasks)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [CI/CD & Security](#cicd--security)
- [Deployment](#deployment)
- [Error Handling](#error-handling)
- [Architecture Decisions](#architecture-decisions)

---

## Overview

Aura is a bilingual (Arabic/English) health companion that provides:

- **Conversational AI chat** — Gemini-powered health guidance with file attachments (skin images, medical reports) analyzed inline via LangGraph
- **Skin analysis** — Upload a skin photo in chat, get AI-powered findings with severity and recommendations
- **Medical report analysis** — Upload a PDF report in chat, get biomarker explanations and next steps
- **Health logging** — Daily mood, energy, sleep, hydration, exercise, symptom tracking
- **Wellness plans** — AI-generated personalized 7-day wellness plans (premium)
- **Support tickets** — In-app support with status tracking
- **Subscriptions** — Stripe-powered free/premium tiers

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115.14 |
| Database | Supabase (Postgres + Auth + Storage) |
| AI | Google Gemini 2.5 Flash |
| Conversation Graph | LangGraph + LangChain Core |
| Billing | Stripe Checkout + Webhooks |
| Task Queue | Celery + Redis (reserved for future use) |
| HTTP Client | httpx + tenacity (retry/timeout) |
| Rate Limiting | slowapi (Redis-backed) |
| Logging | structlog (JSON in production) |
| Error Tracking | Sentry |
| Testing | pytest + pytest-asyncio |

---

## Prerequisites

- Python 3.11+
- Redis 7+ (for Celery broker + rate limiting)
- A Supabase project with the required tables (run migrations below)
- A Google Gemini API key
- Stripe keys (for subscriptions — can be left empty for development)

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/Osama-Abo-Bakr/aura-backend.git
cd aura-backend

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env with your actual values (see Environment Variables below)

# 5. Run database migrations on your Supabase project
# Execute each migration SQL file in order:
#   supabase/migrations/001_initial_schema.sql
#   supabase/migrations/002_add_analysis_status.sql
#   supabase/migrations/003_storage_policies.sql
#   supabase/migrations/004_tickets.sql
#   supabase/migrations/005_add_message_file_columns.sql

# 6. Start Redis (required for rate limiting)
docker compose up redis -d
# Or use any Redis instance and set REDIS_URL in .env

# 7. Start the API server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs` (disabled in production).

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development`, `production`, or `test` |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend URL (used for CORS + Stripe redirects) |
| `SUPABASE_URL` | **Yes** | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | **Yes** | — | Service role key (bypasses RLS) |
| `SUPABASE_JWT_SECRET` | **Yes** | — | JWT secret for token verification |
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini API key |
| `STRIPE_SECRET_KEY` | No | `""` | Stripe secret key (empty = subscriptions disabled) |
| `STRIPE_WEBHOOK_SECRET` | No | `""` | Stripe webhook signing secret |
| `STRIPE_PRICE_ID_PREMIUM` | No | `""` | Stripe price ID for premium plan |
| `REDIS_URL` | No | `redis://localhost:6379` | Redis URL for rate limiting + Celery |
| `SENTRY_DSN` | No | `""` | Sentry DSN (empty = disabled) |

---

## Project Structure

```
aura-backend/
├── app/
│   ├── main.py                     # FastAPI app, CORS, middleware, routes
│   ├── api/v1/
│   │   ├── __init__.py             # Router aggregation (/api/v1 prefix)
│   │   ├── auth.py                 # Auth endpoints
│   │   ├── analysis.py             # Upload URL generation + history
│   │   ├── chat.py                 # Unified chat endpoint (SSE + file attachments)
│   │   ├── health_log.py           # Health log CRUD + summary
│   │   ├── subscriptions.py        # Stripe checkout + webhooks
│   │   ├── tickets.py              # Support tickets + state machine
│   │   └── wellness.py             # Wellness plan generation
│   ├── core/
│   │   ├── config.py               # Pydantic Settings (env vars)
│   │   ├── deps.py                 # Auth dependency, quota checking
│   │   ├── logging_config.py       # Structured logging setup
│   │   ├── middleware.py            # RequestID, access logs, error handlers
│   │   └── security.py             # JWT verification (ES256 + HS256)
│   ├── db/
│   │   └── supabase.py             # Supabase admin client singleton
│   ├── graph/
│   │   ├── __init__.py             # Exports conversation_graph, ConversationState
│   │   ├── state.py               # ConversationState + FileAttachment TypedDicts
│   │   ├── prompts.py              # System prompts for each node
│   │   ├── nodes.py                # LangGraph node functions (router, analyzers, chat)
│   │   └── graph.py                # LangGraph StateGraph wiring
│   ├── models/
│   │   ├── analysis.py             # Upload URL + history models
│   │   ├── chat.py                 # Chat request, SSE event models
│   │   ├── ticket.py               # Ticket CRUD + status models
│   │   ├── user.py                 # Profile, subscription, auth models
│   │   └── wellness.py             # Health log + wellness plan models
│   ├── services/
│   │   ├── auth.py                 # Supabase Auth REST wrapper (httpx + retry)
│   │   ├── gemini.py               # Gemini AI: chat, skin vision, report vision, wellness
│   │   ├── memory.py               # Ambient context builder (analyses + conversation titles)
│   │   ├── storage.py              # Supabase Storage signed URLs + file download
│   │   └── stripe_svc.py           # Stripe checkout + webhook handling
│   └── tasks/
│       ├── celery_app.py           # Celery instance config
│       └── vision_tasks.py         # Reserved for future background tasks
├── supabase/migrations/
│   ├── 001_initial_schema.sql      # All core tables + RLS
│   ├── 002_add_analysis_status.sql # Analysis status column
│   ├── 003_storage_policies.sql    # Storage bucket RLS
│   ├── 004_tickets.sql             # Tickets table + RLS
│   └── 005_add_message_file_columns.sql  # file_path, file_type, analysis_id on messages
├── tests/
│   ├── conftest.py                 # Mocked Supabase client, fixtures
│   ├── test_auth.py                # AuthService unit tests
│   ├── test_auth_endpoints.py      # Auth endpoint integration tests
│   ├── test_tickets.py             # Ticket CRUD + state machine tests
│   ├── test_health_log.py          # Health log summary unit tests
│   ├── test_middleware.py          # Middleware unit tests
│   ├── test_security.py            # JWT verification tests
│   ├── test_analysis.py            # Analysis endpoint tests
│   ├── test_graph.py               # LangGraph router + response formatter tests
│   ├── test_memory.py              # Memory service tests
│   ├── test_integration_chat.py    # Chat request models, SSE events, routing logic
│   └── test_regression_bugs.py    # Regression tests for past bugs
├── streamlit_app/
│   ├── app.py                     # Interactive test dashboard (chat with file upload)
│   ├── Dockerfile                 # Streamlit container
│   └── requirements.txt           # Dashboard-specific deps
├── .github/
│   ├── workflows/ci.yml           # 5-job CI pipeline (lint → security → test → docker → deploy)
│   └── dependabot.yml             # Weekly dependency updates (pip, docker, actions)
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── Procfile
├── railway.toml
└── requirements.txt
```

---

## API Reference

All endpoints are mounted under `/api/v1`. Authenticated endpoints require a `Authorization: Bearer <token>` header.

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | No | Register a new user. Body: `{email, password, full_name}` |
| `POST` | `/auth/token` | No | Sign in with email/password. Returns access + refresh tokens |
| `POST` | `/auth/refresh` | No | Exchange a refresh token for new tokens. Body: `{refresh_token}` |
| `POST` | `/auth/signout` | Yes | Revoke the current session |

**Register** — `POST /api/v1/auth/register`

```json
// Request
{ "email": "user@example.com", "password": "securepass123", "full_name": "Alice" }

// Response 200
{ "user_id": "uuid", "email": "user@example.com", "full_name": "Alice" }
```

**Sign In** — `POST /api/v1/auth/token`

```json
// Request
{ "email": "user@example.com", "password": "securepass123" }

// Response 200
{ "access_token": "jwt...", "refresh_token": "jwt...", "expires_in": 3600, "token_type": "bearer" }
```

**Refresh** — `POST /api/v1/auth/refresh`

```json
// Request
{ "refresh_token": "jwt..." }

// Response 200
{ "access_token": "new-jwt...", "refresh_token": "new-jwt...", "expires_in": 3600, "token_type": "bearer" }
```

### Profile & Me

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/profile` | Yes | Create or update user profile (upsert) |
| `GET` | `/me` | Yes | Get current user's profile + subscription tier |

**Profile Upsert** — `POST /api/v1/auth/profile`

```json
// First sign-in (ProfileCreate)
{ "full_name": "Alice", "language": "ar", "country": "EG" }

// Subsequent updates (ProfileUpdate — all fields optional)
{ "full_name": "Alice Smith", "health_goals": ["stress management", "better sleep"] }
```

**Me** — `GET /api/v1/me`

```json
// Response 200
{
  "profile": { "user_id": "uuid", "full_name": "Alice", "language": "ar", ... },
  "subscription": { "tier": "free", "status": "active" }
}
```

### Chat

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/chat/message` | Yes | Send a message (with optional file attachment), receive SSE-streamed AI response |
| `GET` | `/chat/conversations` | Yes | List user's 20 most recent conversations |
| `GET` | `/chat/conversations/{id}/messages` | Yes | Get all messages in a conversation |
| `GET` | `/chat/conversations/{id}/analysis` | Yes | Get the latest analysis result in a conversation |
| `DELETE` | `/chat/conversations/{id}` | Yes | Delete a conversation and its messages |

Chat messages are processed through a **LangGraph state machine** that routes based on content type:
- **Text-only** → chat responder with ambient memory context
- **Image attachment** → skin analyzer (Gemini Vision)
- **PDF attachment** → report analyzer (Gemini Vision)

Responses are streamed as Server-Sent Events (SSE) with structured event types:
- `content` — text chunks from the AI response
- `analysis_meta` — analysis type and ID when a file was analyzed
- `quota_error` — quota exceeded notification
- `analysis_error` — error during file analysis
- `[DONE]` — stream terminator

**File upload flow:** Clients first call `POST /analysis/upload-url` to get a signed Supabase Storage URL, upload the file directly, then include the `file_path` and `file_type` in the chat message request.

### Analysis

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/analysis/upload-url` | Yes | Generate a signed Supabase Storage upload URL |
| `GET` | `/analysis/history` | Yes | Paginated analysis history (`?page=1&limit=10`) |

Analysis is now performed inline within the chat endpoint via LangGraph. The standalone `/analysis/skin`, `/analysis/report`, and `/analysis/{id}/status` endpoints have been removed.

### Health Log

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/health-log` | Yes | Upsert health log for a date (defaults to today) |
| `GET` | `/health-log` | Yes | List health logs for last N days (`?days=30`) |
| `GET` | `/health-log/summary` | Yes | Aggregated chart data: mood/energy/sleep trends, symptom frequency |
| `GET` | `/health-log/{log_date}` | Yes | Get a specific date's entry |
| `DELETE` | `/health-log/{log_date}` | Yes | Delete a specific date's entry |

### Subscriptions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/subscribe/checkout` | Yes | Create Stripe Checkout Session for premium upgrade |
| `POST` | `/webhooks/stripe` | No | Stripe webhook receiver (signature-verified) |
| `GET` | `/subscribe/status` | Yes | Get user's subscription tier and status |

### Tickets

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/tickets` | Yes | Create a support ticket |
| `GET` | `/tickets` | Yes | List current user's tickets (newest first) |
| `GET` | `/tickets/{id}` | Yes | Get a specific ticket |
| `PATCH` | `/tickets/{id}/status` | Yes | Transition ticket status |

**Create Ticket** — `POST /api/v1/tickets`

```json
// Request
{ "subject": "App crashes on startup", "description": "The app crashes when I open it", "priority": "high" }

// Response 201
{ "id": "uuid", "user_id": "uuid", "subject": "App crashes on startup", "description": "...", "status": "open", "priority": "high", "created_at": "...", "updated_at": "..." }
```

**Status State Machine** — `PATCH /api/v1/tickets/{id}/status`

```
open → in_progress → resolved → closed
                      └──→ closed
```

- `closed` is a terminal state — no transitions allowed from it
- Setting the same status as current is a no-op (returns 200)
- Invalid transitions return `409 Conflict`

### Wellness

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/wellness/plan` | Yes (premium) | Generate AI wellness plan |
| `GET` | `/wellness/plans` | Yes | List user's saved plans (max 10) |
| `GET` | `/wellness/plans/{id}` | Yes | Get a specific wellness plan |

### Infrastructure

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | No | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/ready` | No | Readiness probe — checks DB, Gemini key, Stripe config |

---

## Authentication

All authenticated endpoints require an `Authorization: Bearer <token>` header. The token is a Supabase JWT.

### Token Verification Flow

1. Client obtains a JWT via `/auth/token` or `/auth/register`
2. Client sends the JWT in the `Authorization` header
3. The `get_current_user` dependency verifies the token:
   - First tries **ES256** verification using JWKS from `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`
   - Falls back to **HS256** using `SUPABASE_JWT_SECRET`
   - Validates `aud: "authenticated"` and expiration
   - Verifies `sub` is a valid UUID
4. Returns the decoded JWT payload (contains `sub`, `email`, `role`)

### AuthService (Server-Side Auth)

The `AuthService` class wraps Supabase Auth REST API calls via `httpx` with:

- **10-second timeout** on all requests
- **Automatic retry** (3 attempts, exponential backoff) on `TransportError` (network failures only, not HTTP errors)
- **Structured logging** via `structlog`
- Custom exceptions mapped to HTTP status codes:
  - `DuplicateEmailError` → 400
  - `InvalidCredentialsError` → 401
  - `InvalidRefreshTokenError` → 401
  - `AuthServiceError` → 503 (after retries exhausted)

---

## Rate Limiting & Quotas

### API Rate Limiting

Global rate limit: **200 requests/minute** per IP (Redis-backed via slowapi).

### Quota System

| Interaction Type | Free Tier | Premium Tier |
|-----------------|-----------|-------------|
| Chat messages | 10/month | Unlimited |
| Skin analysis | 3/month | Unlimited |
| Report analysis | 1/month | Unlimited |

Quotas are tracked in the `ai_interactions` table and checked via the `check_quota` dependency before AI operations.

---

## Background Tasks

Celery is configured and available for future background tasks. Skin and report analysis now run inline via the LangGraph conversation graph (no Celery needed for AI analysis).

Start the worker if needed for future tasks:

```bash
celery -A app.tasks.celery_app worker -l info -Q vision,default -c 2
```

---

## Database Migrations

Run these SQL files in order on your Supabase project (via the SQL Editor or `supabase db push`):

| # | File | Description |
|---|------|-------------|
| 001 | `initial_schema.sql` | Core tables: profiles, subscriptions, ai_interactions, conversations, messages, analyses, health_logs, wellness_plans + RLS + triggers |
| 002 | `add_analysis_status.sql` | Adds `status` column to analyses table |
| 003 | `storage_policies.sql` | RLS policies for Supabase Storage `analyses` bucket |
| 004 | `tickets.sql` | Tickets table + RLS + auto-update trigger |
| 005 | `add_message_file_columns.sql` | Adds `file_path`, `file_type`, `analysis_id` columns to messages table |

All tables use Row Level Security (RLS) — users can only access their own data.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage (50% minimum threshold)
pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=50

# Run specific test files
pytest tests/test_auth.py tests/test_auth_endpoints.py tests/test_tickets.py -v

# Run with short tracebacks
pytest tests/ -v --tb=short
```

The test suite uses:

- **Mocked Supabase client** — `conftest.py` patches `supabase.create_client` at module level so no real Supabase connection is needed
- **Mocked Gemini** — `google.generativeai.configure` is patched to prevent real API calls
- **Dependency overrides** — `get_current_user` is overridden in endpoint tests to inject a fake user
- **Service mocking** — `AuthService` and `supabase_admin` are mocked per-test with `unittest.mock.patch`
- **92 tests** covering auth, tickets, health log, middleware, security, analysis, LangGraph routing, memory, chat integration, and regression bugs

---

## CI/CD & Security

All pushes to `main`/`develop` and PRs to `main` run through a 5-job pipeline:

```
┌──────┐   ┌──────────┐
│ Lint │──▶│   Test   │──┐
└──────┘   └──────────┘  │
┌──────────┐             ├──▶┌────────┐   ┌────────┐
│ Security │─────────────│──▶│ Docker │──▶│ Deploy │
└──────────┘             │   └────────┘   └────────┘
                         │   (Trivy scan)   (main only)
```

| Job | Tools | Purpose |
|-----|-------|---------|
| **Lint & Format** | Ruff (lint + format), mypy | Code quality gate |
| **Security Scan** | Bandit (SAST), pip-audit (CVEs), Gitleaks (secrets) | Vulnerability & secret detection |
| **Test & Coverage** | pytest-cov (50% min), Redis service container | Functional correctness + coverage |
| **Docker Build & Scan** | Docker Buildx, Trivy (container + filesystem SARIF) | Image vulnerabilities, misconfigurations |
| **Deploy Gate** | — | Manual gate (main branch only, all checks pass) |

### Security Features

- **Bandit** — Python SAST scan (JSON artifact uploaded)
- **pip-audit** — Dependency vulnerability audit against known CVEs
- **Gitleaks** — Secret detection across full git history
- **Trivy** — Container image scan (CRITICAL/HIGH severity, SARIF to GitHub Security tab) + filesystem misconfiguration scan
- **Dependabot** — Weekly automated dependency updates for pip, Docker, and GitHub Actions
- **Concurrency control** — In-flight CI runs on the same branch are auto-cancelled

### Streamlit Dashboard

An interactive test dashboard is available in `streamlit_app/` for manual API testing:

```bash
# Run locally
cd streamlit_app
pip install -r requirements.txt
streamlit run app.py

# Or via Docker
docker compose up streamlit
```

Provides a UI for all 8 endpoint groups: Auth, Profile, Chat, Analysis, Health Log, Subscriptions, Tickets, Wellness.

---

## Deployment

### Docker

```bash
docker build -t aura-backend .
docker run -p 8000:8000 --env-file .env aura-backend
```

### Railway

The project includes a `railway.toml` configured for Dockerfile-based deployment with health checks on `/health`.

### Environment Checklist

Before deploying to production:

- [ ] Set `ENVIRONMENT=production` (disables `/docs` and `/redoc`)
- [ ] Set all required Supabase keys
- [ ] Set `GEMINI_API_KEY`
- [ ] Set Stripe keys for subscriptions
- [ ] Set `SENTRY_DSN` for error tracking
- [ ] Run all database migrations
- [ ] Create the `analyses` Storage bucket in Supabase dashboard
- [ ] Configure Stripe webhook endpoint to `/api/v1/webhooks/stripe`
- [ ] Set `SUPABASE_JWT_SECRET_TEST` GitHub secret for CI test job
- [ ] Set `CODECOV_TOKEN` GitHub secret for coverage uploads

### Procfile

For platforms like Railway that support Procfiles:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY
worker: celery -A app.tasks.celery_app worker -Q default -c 2 -l info
```

---

## Error Handling

All errors return a consistent JSON envelope:

```json
{
  "error": "error_code",
  "message": "Human-readable description",
  "request_id": "uuid"
}
```

Validation errors include a `errors` array:

```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "errors": [
    { "field": "email", "message": "value is not a valid email address", "type": "value_error.email" }
  ],
  "request_id": "uuid"
}
```

Rate limit errors (429) include upgrade information:

```json
{
  "error": "quota_exceeded",
  "message": "Monthly quota exceeded for chat. Upgrade to premium for unlimited access.",
  "upgrade_url": "https://your-app.com/pricing"
}
```

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Supabase Auth REST API** | Backend calls Supabase Auth via httpx (not the Python client) for full control over retries, timeouts, and error mapping |
| **Service role + RLS** | Backend uses the service role key to bypass RLS, then scopes all queries by `user_id` — avoids per-request client initialization |
| **ES256 + HS256 fallback** | JWT verification tries JWKS/ES256 first, falls back to HS256 — supports both Supabase key types |
| **LangGraph for conversation routing** | A deterministic state machine routes messages to chat, skin analysis, or report analysis nodes based on file type — keeps logic explicit and testable |
| **Inline analysis via LangGraph** | Skin and report analysis run synchronously in the request via LangGraph nodes (no Celery) — simpler architecture, immediate SSE response, easier error handling |
| **Ambient memory injection** | Before responding, the graph fetches the user's last 3 analyses and most recent conversation title as context — gives the AI awareness without explicit history management |
| **SSE streaming with typed events** | Structured event types (`content`, `analysis_meta`, `quota_error`, `analysis_error`, `[DONE]`) let the frontend render analysis cards and errors distinctly from text |
| **slowapi rate limiting** | Redis-backed rate limiting prevents abuse while keeping the architecture stateless |
| **Quota system** | Simple monthly counter in `ai_interactions` — scales well and is easy to audit |
| **httpx + tenacity retry** | Network calls to Supabase Auth retry on transport errors only (not HTTP errors) with exponential backoff |
| **Structlog** | Structured JSON logs in production for searchability, colored console in development for readability |