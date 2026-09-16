import uuid

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ticket_service.app.dependencies import rate_limiter
from ticket_service.app.database import get_db
from ticket_service.app.models import (
    Order,
    OrderItem,
    OrderStatus,
    Ticket,
    TicketStatus,
    TicketTier,
)
from ticket_service.app.schemas import (
    LockRequest,
    LockResponse,
    OrderCreate,
    OrderRead,
)
from ticket_service.app.middleware.auth_middleware import CurrentUser, get_current_user


router = APIRouter(tags=["Purchase"])

LOCK_TTL_MINUTES = 10


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    """
    Return current UTC time as a naive datetime.
    This matches the datetime format used by the database.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _is_lock_expired(ticket: Ticket) -> bool:
    return (
        ticket.locked_until is not None
        and ticket.locked_until < _now()
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /tickets/lock
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/tickets/lock",
    response_model=LockResponse,
    status_code=status.HTTP_200_OK,
    summary="Reserve an available ticket in a tier (10-min TTL)",
    dependencies=[Depends(rate_limiter)],
)
async def lock_ticket(
    payload: LockRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> LockResponse:

    # Identity comes from the verified JWT.
    user_id = current_user.user_id

    # -------------------------------------------------------------------------
    # 1. Make sure the tier exists
    # -------------------------------------------------------------------------

    tier = await db.scalar(
        select(TicketTier).where(
            TicketTier.tier_id == payload.tier_id
        )
    )

    if not tier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tier not found.",
        )

    # -------------------------------------------------------------------------
    # 2. Make sure this user doesn't already have a live lock in this tier
    # -------------------------------------------------------------------------

    existing_lock = await db.scalar(
        select(Ticket).where(
            Ticket.tier_id == payload.tier_id,
            Ticket.locked_by == user_id,
            Ticket.status == TicketStatus.LOCKED,
            Ticket.locked_until > _now(),
        )
    )

    if existing_lock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You already hold ticket {existing_lock.ticket_id} "
                "in this tier. Complete or release it before locking another."
            ),
        )

    # -------------------------------------------------------------------------
    # 3. Atomically grab one available ticket
    #
    # FOR UPDATE + SKIP LOCKED is important under high concurrency.
    # If another transaction has already locked a ticket, we skip it rather
    # than waiting for that transaction.
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # 4. Lock the ticket for this user
    # -------------------------------------------------------------------------

    ticket.status = TicketStatus.LOCKED
    ticket.locked_by = user_id
    ticket.locked_until = _now() + timedelta(
        minutes=LOCK_TTL_MINUTES
    )

    await db.commit()
    await db.refresh(ticket)

    return LockResponse.model_validate(ticket)


# ─────────────────────────────────────────────────────────────────────────────
# POST /orders
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/orders",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm purchase of locked tickets and create an order",
)
async def create_order(
    payload: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> OrderRead:

    # Identity comes from the verified JWT.
    user_id = current_user.user_id

    # -------------------------------------------------------------------------
    # 1. Prevent duplicate ticket IDs in the same request
    # -------------------------------------------------------------------------

    if len(payload.ticket_ids) != len(set(payload.ticket_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate ticket IDs in request.",
        )

    # -------------------------------------------------------------------------
    # 2. Load and lock all requested tickets
    #
    # Ordering by ticket_id gives every transaction the same locking order,
    # reducing the possibility of deadlocks.
    # -------------------------------------------------------------------------

    tickets_result = await db.scalars(
        select(Ticket)
        .where(
            Ticket.ticket_id.in_(payload.ticket_ids)
        )
        .order_by(Ticket.ticket_id)
        .with_for_update()
    )

    tickets = tickets_result.all()

    # -------------------------------------------------------------------------
    # 3. Check that every requested ticket exists
    # -------------------------------------------------------------------------

    found_ids = {ticket.ticket_id for ticket in tickets}

    missing = set(payload.ticket_ids) - found_ids

    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tickets not found: {[str(i) for i in missing]}",
        )

    # -------------------------------------------------------------------------
    # 4. Validate ownership, status and lock expiry
    # -------------------------------------------------------------------------

    errors: list[str] = []

    for ticket in tickets:

        if ticket.status != TicketStatus.LOCKED:
            errors.append(
                f"{ticket.ticket_id}: "
                f"status is '{ticket.status.value}', "
                "expected 'locked'."
            )

        elif ticket.locked_by != user_id:
            errors.append(
                f"{ticket.ticket_id}: locked by a different user."
            )

        elif _is_lock_expired(ticket):
            errors.append(
                f"{ticket.ticket_id}: "
                f"lock expired at {ticket.locked_until}."
            )

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "One or more tickets cannot be purchased.",
                "errors": errors,
            },
        )

    # -------------------------------------------------------------------------
    # 5. Fetch prices for all involved tiers
    # -------------------------------------------------------------------------

    tier_ids = list({
        ticket.tier_id
        for ticket in tickets
    })

    tiers_result = await db.scalars(
        select(TicketTier).where(
            TicketTier.tier_id.in_(tier_ids)
        )
    )

    price_by_tier = {
        tier.tier_id: tier.price
        for tier in tiers_result.all()
    }

    total = sum(
        price_by_tier[ticket.tier_id]
        for ticket in tickets
    )

    # -------------------------------------------------------------------------
    # 6. Create the order
    # -------------------------------------------------------------------------

    order = Order(
        order_id=uuid.uuid4(),
        user_id=user_id,
        total_amount=total,
        status=OrderStatus.PAID,  # Replace with payment gateway flow later
        created_at=_now(),
    )

    db.add(order)

    # Make sure order_id exists before creating OrderItems.
    await db.flush()

    # -------------------------------------------------------------------------
    # 7. Create order items and mark tickets as SOLD
    # -------------------------------------------------------------------------

    for ticket in tickets:

        db.add(
            OrderItem(
                item_id=uuid.uuid4(),
                order_id=order.order_id,
                ticket_id=ticket.ticket_id,
                price_paid=price_by_tier[ticket.tier_id],
            )
        )

        ticket.status = TicketStatus.SOLD
        ticket.locked_by = None
        ticket.locked_until = None

    await db.commit()

    # -------------------------------------------------------------------------
    # 8. Reload order with items
    # -------------------------------------------------------------------------

    order_result = await db.scalar(
        select(Order).where(
            Order.order_id == order.order_id
        )
    )

    await db.refresh(order_result, ["items"])

    return OrderRead.model_validate(order_result)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /tickets/{ticket_id}/lock
# ─────────────────────────────────────────────────────────────────────────────

@router.delete(
    "/tickets/{ticket_id}/lock",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Release a lock early (user cancels before TTL expires)",
)
async def release_lock(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:

    # Identity comes from the verified JWT.
    user_id = current_user.user_id

    # -------------------------------------------------------------------------
    # 1. Find and lock the ticket row
    # -------------------------------------------------------------------------

    ticket = await db.scalar(
        select(Ticket)
        .where(
            Ticket.ticket_id == ticket_id
        )
        .with_for_update()
    )

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found.",
        )

    # -------------------------------------------------------------------------
    # 2. Make sure this user owns the lock
    # -------------------------------------------------------------------------

    if (
        ticket.status != TicketStatus.LOCKED
        or ticket.locked_by != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't hold an active lock on this ticket.",
        )

    # -------------------------------------------------------------------------
    # 3. Release the ticket
    # -------------------------------------------------------------------------

    ticket.status = TicketStatus.AVAILABLE
    ticket.locked_by = None
    ticket.locked_until = None

    await db.commit()