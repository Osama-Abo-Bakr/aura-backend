"""Pydantic models for the tickets API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    """Request body for creating a ticket."""

    subject: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    priority: Literal["low", "medium", "high"] = "medium"


class TicketStatusUpdate(BaseModel):
    """Request body for transitioning a ticket's status."""

    status: Literal["open", "in_progress", "resolved", "closed"]


class TicketResponse(BaseModel):
    """Response model for a ticket."""

    id: UUID
    user_id: UUID
    subject: str
    description: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
