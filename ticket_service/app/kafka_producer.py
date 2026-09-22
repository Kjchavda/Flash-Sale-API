import json
import logging
import os
from typing import Any, Optional
from aiokafka import AIOKafkaProducer

logger = logging.getLogger("ticket_service.kafka_producer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_BOOKING_CONFIRMATION = os.getenv(
    "KAFKA_TOPIC_BOOKING_CONFIRMATION", "booking-confirmations"
)

_producer: Optional[AIOKafkaProducer] = None


async def get_kafka_producer() -> Optional[AIOKafkaProducer]:
    return _producer


async def start_kafka_producer() -> Optional[AIOKafkaProducer]:
    """
    Initialize and start the AIOKafkaProducer.
    Logs warning if Kafka broker is unreachable during startup.
    """
    global _producer
    if _producer is not None:
        return _producer

    try:
        _producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await _producer.start()
        logger.info(f"Kafka Producer started successfully connecting to {KAFKA_BOOTSTRAP_SERVERS}")
        print(f"[system] Kafka Producer started (servers: {KAFKA_BOOTSTRAP_SERVERS}).")
        return _producer
    except Exception as exc:
        logger.warning(
            f"Failed to start Kafka Producer with bootstrap servers '{KAFKA_BOOTSTRAP_SERVERS}': {exc}"
        )
        print(f"[warning] Could not connect to Kafka at {KAFKA_BOOTSTRAP_SERVERS}: {exc}")
        _producer = None
        return None


async def stop_kafka_producer() -> None:
    """
    Gracefully shut down the AIOKafkaProducer.
    """
    global _producer
    if _producer is not None:
        try:
            await _producer.stop()
            logger.info("Kafka Producer stopped gracefully.")
            print("[system] Kafka Producer shut down gracefully.")
        except Exception as exc:
            logger.error(f"Error stopping Kafka Producer: {exc}")
        finally:
            _producer = None


async def publish_booking_confirmation(payload: dict[str, Any]) -> bool:
    """
    Publish booking confirmation event to Kafka topic.
    Returns True if published successfully, False otherwise.
    """
    global _producer
    if _producer is None:
        # Attempt reconnect if producer wasn't initialized on startup
        logger.info("Kafka Producer not running, attempting initialization...")
        await start_kafka_producer()

    if _producer is None:
        logger.error(
            f"Kafka Producer unavailable. Failed to publish booking confirmation event for order {payload.get('order_id')}"
        )
        return False

    try:
        await _producer.send_and_wait(
            topic=KAFKA_TOPIC_BOOKING_CONFIRMATION,
            value=payload,
            key=str(payload.get("order_id", "")).encode("utf-8") if payload.get("order_id") else None,
        )
        logger.info(
            f"Kafka event produced successfully to topic '{KAFKA_TOPIC_BOOKING_CONFIRMATION}' for order {payload.get('order_id')}"
        )
        return True
    except Exception as exc:
        logger.error(
            f"Failed to publish Kafka event for order {payload.get('order_id')} to topic '{KAFKA_TOPIC_BOOKING_CONFIRMATION}': {exc}"
        )
        return False
