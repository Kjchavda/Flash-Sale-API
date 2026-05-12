import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import rate_limiter
from backend.database import get_db
from backend.models import Order, OrderItem, OrderStatus, Ticket, TicketStatus, TicketTier
from backend.schemas import LockRequest, LockResponse, OrderCreate, OrderRead

router = APIRouter(tags=["Purchase"])

LOCK_TTL_MINUTES = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matches DB


def _is_lock_expired(ticket: Ticket) -> bool:
    return ticket.locked_until is not None and ticket.locked_until < _now()


# ── POST /tickets/lock ────────────────────────────────────────────────────────

@router.post(
    "/tickets/lock",
    response_model=LockResponse,
    status_code=status.HTTP_200_OK,
    summary="Reserve an available ticket in a tier (10-min TTL)",
    dependencies=[Depends(rate_limiter)]
)
async def lock_ticket(
    payload: LockRequest,
    db: AsyncSession = Depends(get_db),
) -> LockResponse:
    # Guard: tier must exist
    tier = await db.scalar(
        select(TicketTier).where(TicketTier.tier_id == payload.tier_id)
    )
    if not tier:
        raise HTTPException(status_code=404, detail="Tier not found.")

    # Guard: user must not already hold a live lock in this tier
    existing_lock = await db.scalar(
        select(Ticket).where(
            Ticket.tier_id == payload.tier_id,
            Ticket.locked_by == payload.user_id,
            Ticket.status == TicketStatus.LOCKED,
            Ticket.locked_until > _now(),
        )
    )
    if existing_lock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already hold ticket {existing_lock.ticket_id} in this tier. "
                   f"Complete or release it before locking another.",
        )

    # Core: atomically grab one AVAILABLE ticket.
    # SKIP LOCKED means concurrent requests skip rows already locked by another
    # transaction instead of queuing behind them — crucial under high contention.
    ticket = await db.scalar(
        select(Ticket)
        .where(
            Ticket.tier_id == payload.tier_id,
            Ticket.status == TicketStatus.AVAILABLE,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No tickets available in this tier.",
        )

    ticket.status = TicketStatus.LOCKED
    ticket.locked_by = payload.user_id
    ticket.locked_until = _now() + timedelta(minutes=LOCK_TTL_MINUTES)

    await db.commit()
    await db.refresh(ticket)
    return LockResponse.model_validate(ticket)


# ── POST /orders ──────────────────────────────────────────────────────────────

@router.post(
    "/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm purchase of locked tickets and create an order",
)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
) -> OrderRead:
    if len(payload.ticket_ids) != len(set(payload.ticket_ids)):
        raise HTTPException(status_code=422, detail="Duplicate ticket IDs in request.")

    # Load and lock all requested tickets in one query (deterministic order avoids deadlocks)
    tickets_result = await db.scalars(
        select(Ticket)
        .where(Ticket.ticket_id.in_(payload.ticket_ids))
        .order_by(Ticket.ticket_id)          # deterministic order → no deadlock
        .with_for_update()
    )
    tickets = tickets_result.all()

    # Validate every ticket before writing anything
    found_ids = {t.ticket_id for t in tickets}
    missing = set(payload.ticket_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Tickets not found: {[str(i) for i in missing]}",
        )

    errors: list[str] = []
    for ticket in tickets:
        if ticket.status != TicketStatus.LOCKED:
            errors.append(f"{ticket.ticket_id}: status is '{ticket.status.value}', expected 'locked'.")
        elif ticket.locked_by != payload.user_id:
            errors.append(f"{ticket.ticket_id}: locked by a different user.")
        elif _is_lock_expired(ticket):
            errors.append(f"{ticket.ticket_id}: lock expired at {ticket.locked_until}.")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "One or more tickets cannot be purchased.", "errors": errors},
        )

    # Fetch prices for all tiers in one query
    tier_ids = list({t.tier_id for t in tickets})
    tiers_result = await db.scalars(
        select(TicketTier).where(TicketTier.tier_id.in_(tier_ids))
    )
    price_by_tier = {tier.tier_id: tier.price for tier in tiers_result.all()}

    total = sum(price_by_tier[t.tier_id] for t in tickets)

    # Create order
    order = Order(
        order_id=uuid.uuid4(),
        user_id=payload.user_id,
        total_amount=total,
        status=OrderStatus.PAID,            # plug in payment gateway here
        created_at=_now(),
    )
    db.add(order)
    await db.flush()                        # get order_id before inserting items

    # Create order items + mark tickets SOLD
    for ticket in tickets:
        db.add(OrderItem(
            item_id=uuid.uuid4(),
            order_id=order.order_id,
            ticket_id=ticket.ticket_id,
            price_paid=price_by_tier[ticket.tier_id],
        ))
        ticket.status = TicketStatus.SOLD
        ticket.locked_until = None

    await db.commit()

    # Reload with items for the response
    order_result = await db.scalar(
        select(Order).where(Order.order_id == order.order_id)
    )
    await db.refresh(order_result, ["items"])
    return OrderRead.model_validate(order_result)


# ── DELETE /tickets/{ticket_id}/lock ─────────────────────────────────────────

@router.delete(
    "/tickets/{ticket_id}/lock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Release a lock early (user cancels before TTL expires)",
)
async def release_lock(
    ticket_id: uuid.UUID,
    user_id: uuid.UUID,                     # query param; move to JWT in prod
    db: AsyncSession = Depends(get_db),
) -> None:
    ticket = await db.scalar(
        select(Ticket)
        .where(Ticket.ticket_id == ticket_id)
        .with_for_update()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if ticket.status != TicketStatus.LOCKED or ticket.locked_by != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't hold an active lock on this ticket.",
        )

    ticket.status = TicketStatus.AVAILABLE
    ticket.locked_by = None
    ticket.locked_until = None
    await db.commit()