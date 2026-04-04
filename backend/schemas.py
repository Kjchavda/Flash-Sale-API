import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Shared config ─────────────────────────────────────────────────────────────

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Venue ─────────────────────────────────────────────────────────────────────

class VenueCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1, max_length=500)
    city: str = Field(..., min_length=1, max_length=100)
    max_capacity: int = Field(..., gt=0)


class VenueRead(_Base):
    venue_id: uuid.UUID
    name: str
    address: str
    city: str
    max_capacity: int


# ── Event ─────────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    venue_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sale_start_time: datetime

    @field_validator("sale_start_time")
    @classmethod
    def must_be_future(cls, v: datetime) -> datetime:
        if v <= datetime.utcnow():
            raise ValueError("sale_start_time must be in the future")
        return v


class EventRead(_Base):
    event_id: uuid.UUID
    venue_id: uuid.UUID
    title: str
    description: Optional[str]
    sale_start_time: datetime


# ── TicketTier ────────────────────────────────────────────────────────────────

class TierCreate(BaseModel):
    event_id: uuid.UUID
    tier_name: str = Field(..., min_length=1, max_length=100)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    total_allocated: int = Field(..., gt=0)


class TierRead(_Base):
    tier_id: uuid.UUID
    event_id: uuid.UUID
    tier_name: str
    price: Decimal
    total_allocated: int


# ── Inventory generation ──────────────────────────────────────────────────────

class GenerateInventoryRequest(BaseModel):
    event_id: uuid.UUID


class TierInventorySummary(BaseModel):
    tier_id: uuid.UUID
    tier_name: str
    tickets_created: int


class GenerateInventoryResponse(BaseModel):
    event_id: uuid.UUID
    tiers_processed: int
    total_tickets_created: int
    breakdown: list[TierInventorySummary]