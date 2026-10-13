import pytest
import os
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.testclient import TestClient

from ticket_service.app.dependencies import rate_limiter, MAX_REQUESTS, WINDOW_SECONDS, redis_client


# Helper mini-app to isolate testing the rate_limiter dependency
rate_limit_app = FastAPI()

@rate_limit_app.get("/rate-limited-endpoint", dependencies=[Depends(rate_limiter)])
async def sample_endpoint():
    return {"message": "success"}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Unit & Simulated Rate Limiting Tests (Deterministic, Runs Everywhere)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_allows_under_limit():
    """
    Verify that requests within the allowed threshold (<= MAX_REQUESTS) succeed.
    """
    mock_request = Request({"type": "http", "client": ("192.168.1.10", 12345)})

    # Mock Redis eval returning 1 (Allowed)
    with patch.object(redis_client, "eval", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = 1

        for _ in range(MAX_REQUESTS):
            # Should not raise HTTPException
            await rate_limiter(mock_request)

        assert mock_eval.call_count == MAX_REQUESTS


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_limit_exceeded():
    """
    Verify that when the Redis sliding window indicates limit exceeded (eval returns 0),
    HTTPException with 429 status code is raised.
    """
    mock_request = Request({"type": "http", "client": ("192.168.1.10", 12345)})

    with patch.object(redis_client, "eval", new_callable=AsyncMock) as mock_eval:
        mock_eval.return_value = 0  # Blocked

        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter(mock_request)

        assert exc_info.value.status_code == 429
        assert f"Rate limit exceeded. Try again in {WINDOW_SECONDS} seconds." in exc_info.value.detail


def test_rate_limiter_integration_http_429():
    """
    Integration test via TestClient:
    - 5 requests succeed (HTTP 200)
    - 6th request fails with HTTP 429 Too Many Requests
    """
    call_counts = {}

    async def mock_sliding_window_eval(script, num_keys, key, now_ms, window_ms, limit, member):
        call_counts[key] = call_counts.get(key, 0) + 1
        if call_counts[key] <= limit:
            return 1  # Allowed
        return 0  # Blocked

    with patch.object(redis_client, "eval", side_effect=mock_sliding_window_eval):
        client = TestClient(rate_limit_app)

        # First MAX_REQUESTS (5) should succeed
        for i in range(MAX_REQUESTS):
            res = client.get("/rate-limited-endpoint")
            assert res.status_code == 200, f"Request {i+1} failed with {res.status_code}"
            assert res.json() == {"message": "success"}

        # 6th request must be blocked
        blocked_res = client.get("/rate-limited-endpoint")
        assert blocked_res.status_code == 429
        assert f"Rate limit exceeded. Try again in {WINDOW_SECONDS} seconds." in blocked_res.json()["detail"]


def test_rate_limiter_per_ip_isolation():
    """
    Verify that rate limits are tracked per client IP address.
    If IP-A is blocked, IP-B should still be able to make requests.
    """
    # Track requests per IP key
    counts = {}

    async def mock_eval(script, num_keys, key, now_ms, window_ms, limit, member):
        counts[key] = counts.get(key, 0) + 1
        return 1 if counts[key] <= limit else 0

    with patch.object(redis_client, "eval", side_effect=mock_eval):
        # Client 1
        c1 = TestClient(rate_limit_app, client=("10.0.0.1", 50000))
        # Exceed limit for Client 1
        for _ in range(MAX_REQUESTS):
            assert c1.get("/rate-limited-endpoint").status_code == 200
        assert c1.get("/rate-limited-endpoint").status_code == 429

        # Client 2 (different IP) should still be allowed
        c2 = TestClient(rate_limit_app, client=("10.0.0.2", 50000))
        assert c2.get("/rate-limited-endpoint").status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 2. Live Redis Integration Tests (Runs when Redis service is available, e.g. CI)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limiter_live_redis():
    """
    End-to-end test against a real Redis instance (e.g. in GitHub Actions CI).
    Skipped if local Redis is not running.
    """
    try:
        await redis_client.ping()
    except Exception:
        pytest.skip("Live Redis service not running on configured REDIS_URL")

    test_ip = "127.0.0.99"
    test_key = f"rate_limit:{test_ip}"
    await redis_client.delete(test_key)

    mock_req = Request({"type": "http", "client": (test_ip, 8888)})

    # Send MAX_REQUESTS
    for _ in range(MAX_REQUESTS):
        await rate_limiter(mock_req)

    # 6th should raise 429
    with pytest.raises(HTTPException) as exc_info:
        await rate_limiter(mock_req)
    assert exc_info.value.status_code == 429

    # Clean up key
    await redis_client.delete(test_key)
