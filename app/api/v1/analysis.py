"""
Analysis endpoints — Week 2 implementation.

Routes:
  POST /api/v1/analysis/upload-url   — get a signed Supabase Storage upload URL
  POST /api/v1/analysis/skin         — run skin analysis via Gemini Vision
  GET  /api/v1/analysis/history      — paginated analysis history for the user
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_user, get_current_user_with_tier, make_quota_checker
from app.db.supabase import supabase_admin
from app.services.gemini import VISION_MODEL, analyze_skin
from app.services.storage import download_file, generate_upload_url

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
    summary="Analyze a skin image with Gemini Vision",
    dependencies=[Depends(make_quota_checker("skin"))],
)
async def run_skin_analysis(
    body: SkinAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict:
    """
    Download the uploaded file from Supabase Storage, run Gemini Vision skin
    analysis, persist the result, and return it immediately (synchronous in
    Week 2 — BackgroundTasks wired for future async promotion).
    """
    user_id: str = current_user["sub"]

    # 1. Download the file from storage.
    try:
        image_bytes, content_type = await download_file(body.file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "file_download_failed", "detail": str(exc)},
        )

    # 2. Call Gemini Vision.
    try:
        result = await analyze_skin(image_bytes, content_type, body.language)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "analysis_failed", "detail": str(exc)},
        )

    # 3. Persist to `analyses` table.
    analysis_id = str(uuid.uuid4())
    analysis_row = {
        "id": analysis_id,
        "user_id": user_id,
        "type": "skin",
        "file_path": body.file_path,
        "result_json": result,
        "model_used": VISION_MODEL,
        "language": body.language,
    }
    supabase_admin.table("analyses").insert(analysis_row).execute()

    # 4. Record in `ai_interactions` for quota tracking.
    interaction_row = {
        "user_id": user_id,
        "interaction_type": "skin",
        "model_used": VISION_MODEL,
        "result_json": result,
    }
    supabase_admin.table("ai_interactions").insert(interaction_row).execute()

    # 5. Return the analysis result with the analysis_id.
    return {**result, "analysis_id": analysis_id}


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
