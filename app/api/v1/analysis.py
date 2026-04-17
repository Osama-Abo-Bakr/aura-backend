"""Analysis endpoints — upload URL generation and history."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.db.supabase import supabase_admin
from app.models.analysis import UploadURLRequest
from app.services.storage import generate_upload_url

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.post("/upload-url")
async def create_upload_url(
    request: UploadURLRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a signed URL for uploading a file to Supabase Storage."""
    user_id = user["sub"]
    result = await generate_upload_url(
        user_id=user_id,
        file_name=request.file_name,
        content_type=request.content_type,
    )
    return result


@router.get("/history")
async def get_analysis_history(
    page: int = 1,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """Get paginated analysis history for the user."""
    user_id = user["sub"]
    offset = (page - 1) * limit

    resp = (
        supabase_admin
        .table("analyses")
        .select("id, analysis_type, status, created_at, result")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {"analyses": resp.data, "page": page, "limit": limit}