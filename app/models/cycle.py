from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field


class CycleEntryCreate(BaseModel):
    """Create or update a menstrual cycle entry."""

    start_date: date = Field(..., description="First day of period (YYYY-MM-DD).")
    end_date: date | None = Field(
        default=None, description="Last day of period, null if ongoing."
    )
    cycle_length: int = Field(
        default=28, ge=14, le=45, description="Average cycle length in days."
    )
    period_length: int = Field(
        default=5, ge=1, le=14, description="Average period duration in days."
    )
    symptoms: list[str] = Field(
        default_factory=list, description="Symptoms like cramps, headache, bloating."
    )
    mood: int | None = Field(default=None, ge=1, le=10, description="Mood score 1-10.")
    notes: str | None = Field(default=None, max_length=1000)


class CycleEntryResponse(BaseModel):
    """Response for a single cycle entry."""

    id: UUID
    user_id: UUID
    start_date: date
    end_date: date | None = None
    cycle_length: int = 28
    period_length: int = 5
    symptoms: list[str] = []
    mood: int | None = None
    notes: str | None = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class CyclePrediction(BaseModel):
    """Predicted next period dates and current phase."""

    next_period_start: date
    next_period_end: date
    days_until_next: int
    current_phase: str  # "menstrual" | "follicular" | "ovulation" | "luteal"
    phase_description: str
