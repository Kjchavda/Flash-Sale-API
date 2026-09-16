import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sqlalchemy import text

from ticket_service.app.routers import events, inventory, tiers, venues, purchase
from ticket_service.app.database import Base, engine
from ticket_service.app.dependencies import redis_client
from ticket_service.app.tasks import expired_locks
from ticket_service.app.middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 1. Startup: Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
 
    # 2. Startup: Boot the background sweeper
    scheduler = AsyncIOScheduler()
    scheduler.add_job(expired_locks.reap_expired_locks, 'interval', minutes=1)
    scheduler.start()
    print("[system] Lock Reaper background task started.")

    yield 
    
    # 3. Shutdown: Gracefully stop the scheduler
    scheduler.shutdown()
    print("[system] Lock Reaper shut down gracefully.")


app = FastAPI(
    title="Ticketing API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)

app.include_router(venues.router)
app.include_router(events.router)
app.include_router(tiers.router)
app.include_router(inventory.router)
app.include_router(purchase.router)


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    status = {"status": "ok", "database": "unknown", "redis": "unknown"}
 
    # Check Postgres (Neon)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {e}"
        status["status"] = "error"
 
    # Check Redis (Upstash)
    try:
        # pyrefly: ignore [not-async]
        await redis_client.ping()
        status["redis"] = "ok"
    except Exception as e:
        status["redis"] = f"error: {e}"
        status["status"] = "error"
 
    return status