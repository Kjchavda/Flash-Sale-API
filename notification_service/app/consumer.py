import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger("notification_service.consumer")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [NOTIF-KAFKA-CONSUMER] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_BOOKING_CONFIRMATION = os.getenv(
    "KAFKA_TOPIC_BOOKING_CONFIRMATION", "booking-confirmations"
)
KAFKA_GROUP_ID = os.getenv("KAFKA_GROUP_ID", "notification-service-group")


def _process_booking_confirmation_event(data: dict) -> None:
    order_id = data.get("order_id", "N/A")
    user_id = data.get("user_id", "N/A")
    user_email = data.get("user_email")
    recipient = user_email or f"user-{user_id}@example.com"
    ticket_ids = data.get("ticket_ids", [])
    ticket_count = len(ticket_ids) if ticket_ids else 0
    total_amount = data.get("total_amount")
    if total_amount is not None:
        try:
            amount_str = f"${float(total_amount):.2f}"
        except (ValueError, TypeError):
            amount_str = f"${total_amount}"
    else:
        amount_str = "N/A"
    event_title = data.get("event_title", "Flash Sale Event")
    timestamp = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

    logger.info(
        "\n------------------------------------------------------------------------\n"
        "📧 [DUMMY NOTIFICATION: BOOKING CONFIRMATION - CONSUMED FROM KAFKA]\n"
        f"   Order ID     : {order_id}\n"
        f"   User ID      : {user_id}\n"
        f"   Recipient    : {recipient}\n"
        f"   Event Title  : {event_title}\n"
        f"   Tickets      : {ticket_count} ticket(s) ({[str(t) for t in ticket_ids]})\n"
        f"   Total Amount : {amount_str}\n"
        f"   Timestamp    : {timestamp}\n"
        "   Delivery     : DELIVERED (Simulated Kafka event dispatch)\n"
        "------------------------------------------------------------------------"
    )


async def consume_booking_confirmations() -> None:
    """
    Background worker that continuously consumes booking confirmation events from Kafka.
    Includes connection retry logic for resilient startup.
    """
    logger.info(
        f"Starting Kafka consumer loop for topic '{KAFKA_TOPIC_BOOKING_CONFIRMATION}' "
        f"on {KAFKA_BOOTSTRAP_SERVERS} (group: {KAFKA_GROUP_ID})..."
    )

    while True:
        consumer: AIOKafkaConsumer | None = None
        try:
            consumer = AIOKafkaConsumer(
                KAFKA_TOPIC_BOOKING_CONFIRMATION,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            )
            await consumer.start()
            logger.info(f"Kafka consumer successfully connected and subscribed to '{KAFKA_TOPIC_BOOKING_CONFIRMATION}'.")

            async for message in consumer:
                try:
                    payload = message.value
                    logger.info(
                        f"Received Kafka event from partition {message.partition}, offset {message.offset}"
                    )
                    _process_booking_confirmation_event(payload)
                except Exception as exc:
                    logger.error(f"Error processing Kafka message: {exc}")

        except asyncio.CancelledError:
            logger.info("Kafka consumer task received cancellation request.")
            if consumer:
                await consumer.stop()
            break
        except Exception as exc:
            logger.warning(
                f"Kafka consumer connection error or broker unavailable ({exc}). Retrying in 5 seconds..."
            )
            if consumer:
                try:
                    await consumer.stop()
                except Exception:
                    pass
            await asyncio.sleep(5)
