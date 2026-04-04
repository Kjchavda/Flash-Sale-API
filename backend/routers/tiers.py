import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Event, TicketTier, Venue
from backend.schemas import TierCreate, TierRead

router = APIRouter(prefix="/tiers", tags=["Tiers"])


@router.post(
    "",
    response_model=TierRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a ticket tier for an event",
)
async def create_tier(
    payload: TierCreate,
    db: AsyncSession = Depends(get_db),
) -> TierRead:
    # Guard: event must exist (and load its venue for capacity check)
    event = await db.scalar(
        select(Event).where(Event.event_id == payload.event_id)
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {payload.event_id} not found.",
        )

    # Guard: total allocated across all tiers must not exceed venue capacity
    venue = await db.scalar(
        select(Venue).where(Venue.venue_id == event.venue_id)
    )

    if not venue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Venue {event.venue_id} not found.",
        )

    already_allocated = await db.scalar(
    select(func.coalesce(func.sum(TicketTier.total_allocated), 0)).where(
        TicketTier.event_id == payload.event_id
    )
) or 0
    if already_allocated + payload.total_allocated > venue.max_capacity:
        remaining = venue.max_capacity - already_allocated
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Allocation of {payload.total_allocated} exceeds the venue's remaining "
                f"capacity ({remaining} seats left of {venue.max_capacity})."
            ),
        )

    tier = TicketTier(
        tier_id=uuid.uuid4(),
        event_id=payload.event_id,
        tier_name=payload.tier_name,
        price=payload.price,
        total_allocated=payload.total_allocated,
    )
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return TierRead.model_validate(tier)