import logging
from datetime import datetime, timezone
from fastapi import APIRouter, status

try:
    from app.schemas import BookingConfirmationRequest, NotificationResponse
except ImportError:
    from ..schemas import BookingConfirmationRequest, NotificationResponse

logger = logging.getLogger("notification_service.notify")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [NOTIF-SERVICE] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

router = APIRouter(tags=["Notifications"])


@router.post(
    "/booking-confirmation",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Send dummy booking confirmation notification",
)
async def notify_booking_confirmation(
    payload: BookingConfirmationRequest,
) -> NotificationResponse:
    recipient = payload.user_email or f"user-{payload.user_id}@example.com"
    ticket_count = len(payload.ticket_ids) if payload.ticket_ids else 0
    amount_str = f"${payload.total_amount:.2f}" if payload.total_amount is not None else "N/A"

    # Dummy notification simulation - log booking confirmation details
    logger.info(
        "------------------------------------------------------------------------\n"
        "📧 [DUMMY NOTIFICATION: BOOKING CONFIRMATION]\n"
        f"   Order ID     : {payload.order_id}\n"
        f"   User ID      : {payload.user_id}\n"
        f"   Recipient    : {recipient}\n"
        f"   Event Title  : {payload.event_title or 'N/A'}\n"
        f"   Tickets      : {ticket_count} ticket(s) ({[str(t) for t in (payload.ticket_ids or [])]})\n"
        f"   Total Amount : {amount_str}\n"
        f"   Timestamp    : {payload.timestamp or datetime.now(timezone.utc).isoformat()}\n"
        "   Status       : DELIVERED (Simulated dummy dispatch)\n"
        "------------------------------------------------------------------------"
    )

    return NotificationResponse(
        status="sent",
        message="Booking confirmation notification dispatched successfully (dummy).",
        order_id=payload.order_id,
        recipient=recipient,
        delivered_at=datetime.now(timezone.utc),
    )
