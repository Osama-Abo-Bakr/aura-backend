"""
Analysis endpoints — Week 3 implementation.

Routes:
  POST /api/v1/analysis/upload-url       — get a signed Supabase Storage upload URL
  POST /api/v1/analysis/skin             — dispatch async skin analysis via Celery
  POST /api/v1/analysis/report           — dispatch async medical report analysis via Celery
  GET  /api/v1/analysis/{id}/status      — poll status / result for any analysis
  GET  /api/v1/analysis/history          — paginated analysis history for the user
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user, make_quota_checker
from app.db.supabase import supabase_admin
from app.services.storage import generate_upload_url

router = APIRouter(prefix="/analysis")

# ---------------------------------------------------------------------------
# Allowed MIME types for upload
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class UploadURLRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str


class UploadURLResponse(BaseModel):
    upload_url: str
    file_path: str


class SkinAnalysisRequest(BaseModel):
    file_path: str
    language: Literal["en", "ar"] = "en"


class ReportAnalysisRequest(BaseModel):
    file_path: str
    language: Literal["en", "ar"] = "en"


class HistoryResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    limit: int


# ---------------------------------------------------------------------------
# POST /analysis/upload-url
# ---------------------------------------------------------------------------


@router.post(
    "/upload-url",
    response_model=UploadURLResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate a signed Supabase Storage upload URL",
)
async def get_upload_url(
    body: UploadURLRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UploadURLResponse:
    """
    Returns a short-lived pre-signed PUT URL that the client uses to upload
    a file directly to Supabase Storage without routing bytes through the API.
    """
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "unsupported_content_type",
                "allowed": sorted(ALLOWED_CONTENT_TYPES),
                "received": body.content_type,
            },
        )

    user_id: str = current_user["sub"]
    result = generate_upload_url(user_id, body.file_name, body.content_type)
    return UploadURLResponse(**result)


# ---------------------------------------------------------------------------
# POST /analysis/skin
# ---------------------------------------------------------------------------


@router.post(
    "/skin",
    status_code=status.HTTP_200_OK,
    summary="Dispatch async skin analysis via Celery",
    dependencies=[Depends(make_quota_checker("skin"))],
)
async def run_skin_analysis(
    body: SkinAnalysisRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Insert a pending analyses row, dispatch a Celery task for Gemini Vision
    skin analysis, and return immediately so the client can poll for completion.
    """
    from app.tasks.vision_tasks import process_skin_analysis

    user_id: str = current_user["sub"]
    analysis_id = str(uuid.uuid4())

    # 1. Insert pending row.
    supabase_admin.table("analyses").insert(
        {
            "id": analysis_id,
            "user_id": user_id,
            "analysis_type": "skin",
            "file_path": body.file_path,
            "language": body.language,
            "status": "processing",
        }
    ).execute()

    # 2. Dispatch Celery task.
    process_skin_analysis.delay(analysis_id, body.file_path, body.language, user_id)

    # 3. Return immediately.
    return {"analysis_id": analysis_id, "status": "processing"}


# ---------------------------------------------------------------------------
# POST /analysis/report
# ---------------------------------------------------------------------------


@router.post(
    "/report",
    status_code=status.HTTP_200_OK,
    summary="Dispatch async medical report analysis via Celery",
    dependencies=[Depends(make_quota_checker("report"))],
)
async def run_report_analysis(
    body: ReportAnalysisRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Insert a pending analyses row, dispatch a Celery task for Gemini Vision
    medical report analysis, and return immediately so the client can poll.
    """
    from app.tasks.vision_tasks import process_report_analysis

    user_id: str = current_user["sub"]
    analysis_id = str(uuid.uuid4())

    # 1. Insert pending row.
    supabase_admin.table("analyses").insert(
        {
            "id": analysis_id,
            "user_id": user_id,
            "analysis_type": "report",
            "file_path": body.file_path,
            "language": body.language,
            "status": "processing",
        }
    ).execute()

    # 2. Dispatch Celery task.
    process_report_analysis.delay(analysis_id, body.file_path, body.language, user_id)

    # 3. Return immediately.
    return {"analysis_id": analysis_id, "status": "processing"}


# ---------------------------------------------------------------------------
# GET /analysis/{id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/{analysis_id}/status",
    status_code=status.HTTP_200_OK,
    summary="Poll the status and result of an analysis job",
)
async def get_analysis_status(
    analysis_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Fetch the current status (and result once completed) for a given analysis.
    Returns 404 if the analysis does not exist or belongs to a different user.
    """
    user_id: str = current_user["sub"]

    resp = (
        supabase_admin.table("analyses")
        .select("id, user_id, status, result, analysis_type, created_at")
        .eq("id", analysis_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    row = resp.data
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "analysis_not_found"},
        )

    return {
        "analysis_id": row["id"],
        "status": row["status"],
        "result": row.get("result"),
        "type": row["analysis_type"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# GET /analysis/history
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Paginated analysis history for the authenticated user",
)
async def get_analysis_history(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    limit: int = Query(default=10, ge=1, le=50, description="Items per page (max 50)"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> HistoryResponse:
    """
    Return the authenticated user's analysis history ordered newest-first.
    """
    user_id: str = current_user["sub"]
    offset = (page - 1) * limit

    # Count total rows first.
    count_resp = (
        supabase_admin.table("analyses")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    total: int = count_resp.count or 0

    # Fetch the requested page.
    rows_resp = (
        supabase_admin.table("analyses")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return HistoryResponse(
        items=rows_resp.data or [],
        total=total,
        page=page,
        limit=limit,
    )
