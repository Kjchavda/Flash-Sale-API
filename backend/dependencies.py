import os
import redis.asyncio as redis
from fastapi import HTTPException, Request, status
from dotenv import load_dotenv

load_dotenv()

# Initialize the Upstash Redis client
redis_client = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# Configuration: Limit users to 5 requests per 10 seconds
MAX_REQUESTS = 5
WINDOW_SECONDS = 10

async def rate_limiter(request: Request):
    """
    A fast, Redis-backed rate limiter dependency.
    Blocks IPs that exceed MAX_REQUESTS within WINDOW_SECONDS.
    """
    # In production behind a proxy, use request.headers.get("X-Forwarded-For")
    client_ip = request.client.host if request.client else "unknown"
    redis_key = f"rate_limit:{client_ip}"

    # Increment the counter for this IP
    current_requests = await redis_client.incr(redis_key)

    # If this is their first request in the window, set the expiration timer
    if current_requests == 1:
        await redis_client.expire(redis_key, WINDOW_SECONDS)

    # If they hit the limit, bounce them instantly
    if current_requests > MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {WINDOW_SECONDS} seconds."
        )