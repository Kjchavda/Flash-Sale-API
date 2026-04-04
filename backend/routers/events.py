import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Event, Venue
from backend.schemas import EventCreate, EventRead

router = APIRouter(prefix="/events", tags=["Events"])


@router.post(
    "",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
)
async def create_event(
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
) -> EventRead:
    # Guard: venue must exist
    venue = await db.scalar(
        select(Venue).where(Venue.venue_id == payload.venue_id)
    )
    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue {payload.venue_id} not found.",
        )

    event = Event(
        event_id=uuid.uuid4(),
        venue_id=payload.venue_id,
        title=payload.title,
        description=payload.description,
        sale_start_time=payload.sale_start_time,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return EventRead.model_validate(event)