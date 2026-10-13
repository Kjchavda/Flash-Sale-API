import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from ticket_service.app.models import (
    Event,
    Order,
    OrderStatus,
    Ticket,
    TicketStatus,
    TicketTier,
    Venue,
)
from ticket_service.app.dependencies import rate_limiter
from ticket_service.app.main import app


async def create_test_event_and_tier(
    db_session,
    total_allocated: int = 3,
    price: float = 85.00,
):
    """
    Helper function to seed Venue -> Event -> TicketTier -> Tickets in the test DB.
    """
    venue = Venue(
        venue_id=uuid.uuid4(),
        name=f"Grand Arena {uuid.uuid4().hex[:6]}",
        address="100 Main St",
        city="Metropolis",
        max_capacity=500,
    )
    db_session.add(venue)
    await db_session.flush()

    event = Event(
        event_id=uuid.uuid4(),
        venue_id=venue.venue_id,
        title="Flash Sale Mega Fest",
        sale_start_time=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db_session.add(event)
    await db_session.flush()

    tier = TicketTier(
        tier_id=uuid.uuid4(),
        event_id=event.event_id,
        tier_name="VIP Pass",
        price=price,
        total_allocated=total_allocated,
    )
    db_session.add(tier)
    await db_session.flush()

    tickets = [
        Ticket(
            ticket_id=uuid.uuid4(),
            tier_id=tier.tier_id,
            status=TicketStatus.AVAILABLE,
        )
        for _ in range(total_allocated)
    ]
    db_session.add_all(tickets)
    await db_session.commit()
    await db_session.refresh(tier)

    return venue, event, tier, tickets


@pytest.fixture(autouse=True)
def bypass_rate_limiter_for_booking_tests():
    """
    Bypass rate limiting dependency during core booking logic tests.
    Dedicated rate limit tests live in test_rate_limit.py.
    """
    app.dependency_overrides[rate_limiter] = lambda: None
    yield
    app.dependency_overrides.pop(rate_limiter, None)


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Successful Ticket Lock (POST /tickets/lock)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lock_ticket_success(client, db_session, auth_headers):
    """
    Test 1: Verify a user can successfully lock an available ticket in a tier.
    - Status code should be 200 OK
    - Returned ticket status must be 'locked'
    - locked_by matches the authenticated user ID
    - locked_until is set into the future
    """
    headers, user_id = auth_headers()
    _, _, tier, _ = await create_test_event_and_tier(db_session, total_allocated=2)

    response = client.post(
        "/tickets/lock",
        json={"tier_id": str(tier.tier_id)},
        headers=headers,
    )

    assert response.status_code == 200, f"Expected 200, got: {response.text}"
    data = response.json()
    assert data["tier_id"] == str(tier.tier_id)
    assert data["status"] == "locked"
    assert data["locked_until"] is not None

    # Verify directly in the database (expire identity map to see committed API update)
    db_session.expire_all()
    locked_ticket_id = uuid.UUID(data["ticket_id"])
    db_ticket = await db_session.scalar(
        select(Ticket).where(Ticket.ticket_id == locked_ticket_id)
    )
    assert db_ticket is not None
    assert db_ticket.status == TicketStatus.LOCKED
    assert db_ticket.locked_by == user_id


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Double Lock Conflict Prevention (POST /tickets/lock -> 409 Conflict)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lock_ticket_conflict_already_held(client, db_session, auth_headers):
    """
    Test 2: Anti-hoarding & Conflict Prevention
    Verify a user CANNOT lock a second ticket in the same tier while holding an active lock.
    - First lock succeeds (200 OK)
    - Second lock by the same user in the same tier returns 409 CONFLICT
    """
    headers, user_id = auth_headers()
    _, _, tier, _ = await create_test_event_and_tier(db_session, total_allocated=5)

    # 1. First lock succeeds
    first_res = client.post(
        "/tickets/lock",
        json={"tier_id": str(tier.tier_id)},
        headers=headers,
    )
    assert first_res.status_code == 200

    # 2. Second lock by the same user in the same tier fails with 409 Conflict
    second_res = client.post(
        "/tickets/lock",
        json={"tier_id": str(tier.tier_id)},
        headers=headers,
    )
    assert second_res.status_code == 409
    error_data = second_res.json()
    assert "already hold ticket" in error_data["detail"]


@pytest.mark.asyncio
async def test_lock_ticket_conflict_no_tickets_available(client, db_session, auth_headers):
    """
    Test 2 (Alternate Conflict): When tier inventory is exhausted (0 available tickets),
    locking returns 409 CONFLICT ("No tickets available in this tier.").
    """
    headers1, user1_id = auth_headers()
    headers2, user2_id = auth_headers()
    # Create tier with only 1 ticket
    _, _, tier, _ = await create_test_event_and_tier(db_session, total_allocated=1)

    # User 1 locks the only available ticket
    res1 = client.post("/tickets/lock", json={"tier_id": str(tier.tier_id)}, headers=headers1)
    assert res1.status_code == 200

    # User 2 tries to lock in the same tier
    res2 = client.post("/tickets/lock", json={"tier_id": str(tier.tier_id)}, headers=headers2)
    assert res2.status_code == 409
    assert "No tickets available" in res2.json()["detail"]


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Create Order & Complete Purchase (POST /orders -> 201 Created)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_order_success(client, db_session, auth_headers):
    """
    Test 3: Purchase Completion and Order Creation
    Verify a user can purchase their locked ticket and create an order.
    - Lock ticket
    - POST /orders with ticket_id
    - Status code should be 201 CREATED
    - Order status should be 'paid'
    - Total amount matches tier price
    - Database ticket status transitions from 'locked' to 'sold'
    """
    headers, user_id = auth_headers()
    tier_price = 120.00
    _, _, tier, _ = await create_test_event_and_tier(
        db_session, total_allocated=2, price=tier_price
    )

    # 1. Lock a ticket
    lock_res = client.post(
        "/tickets/lock",
        json={"tier_id": str(tier.tier_id)},
        headers=headers,
    )
    assert lock_res.status_code == 200
    ticket_id = lock_res.json()["ticket_id"]

    # 2. Purchase the locked ticket
    order_res = client.post(
        "/orders",
        json={"ticket_ids": [ticket_id]},
        headers=headers,
    )
    assert order_res.status_code == 201, f"Expected 201, got: {order_res.text}"
    order_data = order_res.json()
    assert order_data["status"] == "paid"
    assert float(order_data["total_amount"]) == pytest.approx(tier_price)
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["ticket_id"] == ticket_id

    # 3. Verify in database: ticket status is SOLD and lock fields are cleared
    db_session.expire_all()
    purchased_ticket = await db_session.scalar(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    assert purchased_ticket is not None
    assert purchased_ticket.status == TicketStatus.SOLD
    assert purchased_ticket.locked_by is None
    assert purchased_ticket.locked_until is None


# ─────────────────────────────────────────────────────────────────────────────
# Bonus: Early Lock Release (DELETE /tickets/{id}/lock -> 204 No Content)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_release_lock_early(client, db_session, auth_headers):
    """
    Verify early cancellation: user locks a ticket then releases it early.
    Ticket reverts to 'available' status.
    """
    headers, user_id = auth_headers()
    _, _, tier, _ = await create_test_event_and_tier(db_session, total_allocated=1)

    # Lock ticket
    lock_res = client.post("/tickets/lock", json={"tier_id": str(tier.tier_id)}, headers=headers)
    assert lock_res.status_code == 200
    ticket_id = lock_res.json()["ticket_id"]

    # Release lock
    del_res = client.delete(f"/tickets/{ticket_id}/lock", headers=headers)
    assert del_res.status_code == 204

    # Verify ticket is available again in DB
    db_session.expire_all()
    ticket = await db_session.scalar(
        select(Ticket).where(Ticket.ticket_id == uuid.UUID(ticket_id))
    )
    assert ticket.status == TicketStatus.AVAILABLE
    assert ticket.locked_by is None
