from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


class ProfileCreate(BaseModel):
    """Payload sent by the client after Supabase auth sign-up."""

    full_name: str = Field(..., min_length=1, max_length=120)
    date_of_birth: datetime | None = None
    language: Literal["ar", "en"] = "ar"
    country: str | None = Field(default=None, max_length=2)  # ISO 3166-1 alpha-2


class ProfileUpdate(BaseModel):
    """All fields are optional — partial updates are allowed."""

    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: datetime | None = None
    language: Literal["ar", "en"] | None = None
    country: str | None = Field(default=None, max_length=2)
    avatar_url: str | None = None
    health_goals: list[str] | None = None
    conditions: list[str] | None = None  # self-reported chronic conditions


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    full_name: str
    date_of_birth: datetime | None = None
    language: str
    country: str | None = None
    avatar_url: str | None = None
    health_goals: list[str] = []
    conditions: list[str] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------


class SubscriptionResponse(BaseModel):
    id: UUID
    user_id: UUID
    tier: Literal["free", "premium"]
    status: Literal["active", "cancelled", "past_due", "trialing"]
    current_period_end: datetime | None = None
    stripe_subscription_id: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
