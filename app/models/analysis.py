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
# Skin analysis
# ---------------------------------------------------------------------------


class SkinAnalysisRequest(BaseModel):
    file_path: str = Field(
        ..., description="Storage path returned by UploadURLResponse"
    )
    language: Literal["ar", "en"] = "ar"
    notes: str | None = Field(default=None, max_length=500)


class SkinFinding(BaseModel):
    condition: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Literal["mild", "moderate", "severe"] | None = None
    recommendations: list[str] = []


class SkinAnalysisResponse(BaseModel):
    analysis_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    findings: list[SkinFinding] = []
    summary: str | None = None
    disclaimer: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Medical report analysis
# ---------------------------------------------------------------------------


class ReportAnalysisRequest(BaseModel):
    file_path: str = Field(
        ..., description="Storage path returned by UploadURLResponse"
    )
    language: Literal["ar", "en"] = "ar"
    report_type: str | None = Field(
        default=None,
        max_length=100,
        examples=["blood_test", "hormone_panel", "thyroid_panel", "ultrasound"],
    )
    notes: str | None = Field(default=None, max_length=500)


class ReportBiomarker(BaseModel):
    name: str
    value: str
    unit: str | None = None
    reference_range: str | None = None
    status: Literal["normal", "low", "high", "critical"] | None = None
    explanation: str | None = None


class ReportAnalysisResponse(BaseModel):
    analysis_id: UUID
    status: Literal["queued", "processing", "completed", "failed"]
    report_type: str | None = None
    biomarkers: list[ReportBiomarker] = []
    summary: str | None = None
    recommendations: list[str] = []
    disclaimer: str
    created_at: datetime


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
