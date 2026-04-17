from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Storage upload helpers
# ---------------------------------------------------------------------------


class UploadURLRequest(BaseModel):
    """Client requests a signed upload URL before uploading a file."""

    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., examples=["image/jpeg", "application/pdf"])
    analysis_type: Literal["skin", "report"]


class UploadURLResponse(BaseModel):
    upload_url: str  # pre-signed PUT URL
    file_path: str  # storage path to reference when triggering analysis
    expires_in: int  # seconds until the signed URL expires


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class AnalysisHistoryItem(BaseModel):
    id: UUID
    analysis_type: Literal["skin", "report"]
    status: Literal["queued", "processing", "completed", "failed"]
    file_path: str
    result_summary: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
