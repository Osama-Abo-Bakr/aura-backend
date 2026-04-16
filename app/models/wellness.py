from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Health Log
# ---------------------------------------------------------------------------


class HealthLogCreate(BaseModel):
    log_date: date = Field(
        ..., description="Date the log entry refers to (YYYY-MM-DD)."
    )
    mood: int | None = Field(default=None, ge=1, le=10, description="Mood score 1–10.")
    energy: int | None = Field(
        default=None, ge=1, le=10, description="Energy score 1–10."
    )
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    water_ml: int | None = Field(default=None, ge=0)
    exercise_minutes: int | None = Field(default=None, ge=0)
    symptoms: list[str] | None = None
    notes: str | None = Field(default=None, max_length=1000)
    # Flexible extra data (e.g., menstrual cycle, medications)
    metadata: dict[str, Any] | None = None


class HealthLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    log_date: date
    mood: int | None = None
    energy: int | None = None
    sleep_hours: float | None = None
    water_ml: int | None = None
    exercise_minutes: int | None = None
    symptoms: list[str] = []
    notes: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Wellness Plan
# ---------------------------------------------------------------------------


class WellnessPlanTask(BaseModel):
    title: str
    description: str | None = None
    frequency: Literal["daily", "weekly", "monthly", "once"] = "daily"
    category: str | None = Field(
        default=None,
        examples=["nutrition", "exercise", "mental_health", "sleep", "hydration"],
    )


class WellnessPlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str | None = None
    tasks: list[WellnessPlanTask] = []
    start_date: date | None = None
    end_date: date | None = None
    generated_by_ai: bool = True
    language: Literal["ar", "en"] = "ar"
    created_at: datetime

    model_config = {"from_attributes": True}
