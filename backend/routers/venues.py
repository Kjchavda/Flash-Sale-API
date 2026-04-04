import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Venue
from backend.schemas import VenueCreate, VenueRead

router = APIRouter(prefix="/venues", tags=["Venues"])


@router.post(
    "",
    response_model=VenueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a venue",
)
async def create_venue(
    payload: VenueCreate,
    db: AsyncSession = Depends(get_db),
) -> VenueRead:
    # Guard: name must be unique per city
    existing = await db.scalar(
        select(Venue).where(
            Venue.name == payload.name,
            Venue.city == payload.city,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A venue named '{payload.name}' already exists in {payload.city}.",
        )

    venue = Venue(
        venue_id=uuid.uuid4(),
        name=payload.name,
        address=payload.address,
        city=payload.city,
        max_capacity=payload.max_capacity,
    )
    db.add(venue)
    await db.commit()
    await db.refresh(venue)
    return VenueRead.model_validate(venue)