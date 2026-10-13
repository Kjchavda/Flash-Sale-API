import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from notification_service.app.main import app as notif_app
from notification_service.app.consumer import _process_booking_confirmation_event
from ticket_service.app.kafka_producer import publish_booking_confirmation
from ticket_service.app.routers.purchase import _notify_booking_confirmed
from ticket_service.app.models import Order, OrderStatus


@pytest.fixture
def notif_client():
    """
    TestClient configured for the Notification Service FastAPI application.
    """
    with TestClient(notif_app) as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# 1. Notification Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_notification_endpoint_success(notif_client):
    """
    Test 1: Send a booking confirmation notification via POST /booking-confirmation
    - Status code should be 200 OK
    - Status in response body should be 'sent'
    - Recipient should match the provided email
    - Order ID in response matches the input payload
    """
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()
    ticket_id = uuid.uuid4()
    email = "attendee@example.com"

    payload = {
        "order_id": str(order_id),
        "user_id": str(user_id),
        "user_email": email,
        "event_title": "Grand Flash Sale Concert",
        "ticket_ids": [str(ticket_id)],
        "total_amount": "150.00",
    }

    response = notif_client.post("/booking-confirmation", json=payload)
    assert response.status_code == 200, f"Expected 200, got: {response.text}"

    data = response.json()
    assert data["status"] == "sent"
    assert data["order_id"] == str(order_id)
    assert data["recipient"] == email
    assert "delivered_at" in data


def test_notification_endpoint_default_recipient(notif_client):
    """
    Verify fallback recipient format when user_email is not provided:
    Defaults to user-{user_id}@example.com
    """
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()

    payload = {
        "order_id": str(order_id),
        "user_id": str(user_id),
        "ticket_ids": [str(uuid.uuid4())],
        "total_amount": "50.00",
    }

    response = notif_client.post("/booking-confirmation", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["recipient"] == f"user-{user_id}@example.com"


def test_notification_endpoint_validation_error(notif_client):
    """
    Test 2: Schema validation error when required fields (e.g. order_id) are missing.
    - Status code should be 422 Unprocessable Entity
    """
    payload = {
        # order_id is missing
        "user_id": str(uuid.uuid4()),
        "total_amount": "75.00",
    }

    response = notif_client.post("/booking-confirmation", json=payload)
    assert response.status_code == 422


def test_notification_service_health(notif_client):
    """
    Verify Notification Service health check endpoint returns 200 OK.
    """
    response = notif_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "notification-service",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Notification Consumer & Producer Logic Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_consumer_process_booking_confirmation_event():
    """
    Test 3: Verify the Kafka consumer message parsing and dummy logger processor
    handles raw event dictionary safely without throwing exceptions.
    """
    sample_kafka_event = {
        "order_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "user_email": "fan@example.com",
        "ticket_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        "total_amount": 200.0,
        "event_title": "Summer Festival",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Should execute without errors or exceptions
    _process_booking_confirmation_event(sample_kafka_event)


@pytest.mark.asyncio
async def test_ticket_service_publish_booking_confirmation():
    """
    Test 4: Verify ticket_service producer publishing helper:
    When Kafka is not running, gracefully catches exception and returns False without failing.
    """
    payload = {
        "order_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "ticket_ids": [str(uuid.uuid4())],
    }

    # Testing resilience: should return boolean (False when disconnected) without raising unhandled exception
    res = await publish_booking_confirmation(payload)
    assert isinstance(res, bool)


@pytest.mark.asyncio
async def test_notify_booking_confirmed_calls_kafka_producer():
    """
    Test 5: Verify _notify_booking_confirmed formats order details correctly
    and passes them to the Kafka producer.
    """
    order_id = uuid.uuid4()
    user_id = uuid.uuid4()
    t_id = uuid.uuid4()

    mock_order = Order(
        order_id=order_id,
        user_id=user_id,
        total_amount=120.00,
        status=OrderStatus.PAID,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )

    with patch(
        "ticket_service.app.routers.purchase.publish_booking_confirmation",
        new_callable=AsyncMock,
    ) as mock_pub:
        mock_pub.return_value = True

        await _notify_booking_confirmed(
            order=mock_order,
            ticket_ids=[t_id],
            user_email="buyer@example.com",
        )

        mock_pub.assert_called_once()
        called_payload = mock_pub.call_args[0][0]
        assert called_payload["order_id"] == str(order_id)
        assert called_payload["user_id"] == str(user_id)
        assert called_payload["user_email"] == "buyer@example.com"
        assert called_payload["ticket_ids"] == [str(t_id)]
        assert called_payload["total_amount"] == 120.00
