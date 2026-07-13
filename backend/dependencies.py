import os
import time
import uuid
from redis.asyncio import Redis, from_url
from fastapi import HTTPException, Request, status
from dotenv import load_dotenv

load_dotenv()

redis_client: Redis = from_url(os.getenv("REDIS_URL"), decode_responses = True)

MAX_REQUESTS = 5
WINDOW_SECONDS = 10

# Lua Script: Atomic Sliding Window Log using Redis ZSET
# Redis guarantees that scripts execute atomically, preventing race conditions.
LUA_SCRIPT = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

local clear_before = now_ms - window_ms

-- 1. Remove timestamps older than the sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

-- 2. Count how many requests are currently in the valid window
local count = redis.call('ZCARD', key)

if count < limit then
    -- 3a. If within limit, add the new request timestamp
    redis.call('ZADD', key, now_ms, member)
    -- 4. Update the key's TTL so it doesn't linger forever
    redis.call('PEXPIRE', key, window_ms)
    return 1 -- Allowed
else
    -- 3b. Hit the limit
    return 0 -- Blocked
end
"""

async def rate_limiter(request: Request):
    """
    Redis-backed sliding window rate limiter dependency.
    Blocks IPs that exceed MAX_REQUESTS within a rolling WINDOW_SECONDS.
    """

    client_ip = request.client.host if request.client else "unknown"
    redis_key = f"rate_limit:{client_ip}"

    now_ms = int(time.time()*1000)
    window_ms = WINDOW_SECONDS*1000

    # Generate a unique member string. 
    # Since Redis ZSETs require unique members, combining the timestamp 
    # with a UUID prevents collisions if multiple requests hit in the exact same millisecond.
    member = f"{now_ms}-{uuid.uuid4()}"

    # Execute the Lua script
    # signature: eval(script, num_keys, key1, arg1, arg2, arg3...)
    is_allowed = await redis_client.eval(
        LUA_SCRIPT,
        1,
        redis_key,
        now_ms,
        window_ms,
        MAX_REQUESTS,
        member
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {WINDOW_SECONDS} seconds."
        )