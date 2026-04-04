import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Event, Ticket, TicketStatus, TicketTier
from backend.schemas import (
    GenerateInventoryRequest,
    GenerateInventoryResponse,
    TierInventorySummary,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.post(
    "/generate-inventory",
    response_model=GenerateInventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk-create AVAILABLE tickets for every tier of an event",
)
async def generate_inventory(
    payload: GenerateInventoryRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateInventoryResponse:
    # Guard: event must exist
    event = await db.scalar(
        select(Event).where(Event.event_id == payload.event_id)
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {payload.event_id} not found.",
        )

    # Fetch all tiers for this event
    tiers_result = await db.scalars(
        select(TicketTier).where(TicketTier.event_id == payload.event_id)
    )
    tiers = tiers_result.all()

    if not tiers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No ticket tiers found for this event. Create tiers before generating inventory.",
        )

    # Guard: idempotency — block re-generation if tickets already exist
    already_exists = await db.scalar(
        select(Ticket.ticket_id)
        .join(TicketTier, Ticket.tier_id == TicketTier.tier_id)
        .where(TicketTier.event_id == payload.event_id)
        .limit(1)
    )
    if already_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inventory already exists for this event. Delete existing tickets before regenerating.",
        )

    # Build the bulk insert payload and per-tier summary in one pass
    rows: list[dict] = []
    breakdown: list[TierInventorySummary] = []

    for tier in tiers:
        tier_rows = [
            {
                "ticket_id": uuid.uuid4(),
                "tier_id": tier.tier_id,
                "locked_by": None,
                "status": TicketStatus.AVAILABLE,
                "locked_until": None,
            }
            for _ in range(tier.total_allocated)
        ]
        rows.extend(tier_rows)
        breakdown.append(
            TierInventorySummary(
                tier_id=tier.tier_id,
                tier_name=tier.tier_name,
                tickets_created=tier.total_allocated,
            )
        )

    # Single bulk INSERT — vastly faster than individual db.add() calls
    await db.execute(insert(Ticket), rows)
    await db.commit()

    return GenerateInventoryResponse(
        event_id=payload.event_id,
        tiers_processed=len(tiers),
        total_tickets_created=len(rows),
        breakdown=breakdown,
    )