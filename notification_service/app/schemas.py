import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class BookingConfirmationRequest(BaseModel):
    order_id: uuid.UUID = Field(..., description="Unique ID of the confirmed order")
    user_id: uuid.UUID = Field(..., description="User ID associated with the booking")
    user_email: Optional[str] = Field(None, description="Email address of the recipient")
    event_title: Optional[str] = Field(None, description="Title of the event")
    ticket_ids: Optional[List[uuid.UUID]] = Field(default_factory=list, description="List of booked ticket IDs")
    total_amount: Optional[Decimal] = Field(None, description="Total amount paid")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Time when booking was placed")


class NotificationResponse(_Base):
    status: str
    message: str
    order_id: uuid.UUID
    recipient: Optional[str] = None
    delivered_at: datetime
