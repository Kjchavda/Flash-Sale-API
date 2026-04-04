import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from backend.database import Base, engine
from backend.routers import events, inventory, tiers, venues, purchase
from backend.tasks import expired_locks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
 
    # Sweep expired locks back to AVAILABLE every 60 s.
    # Replace with APScheduler / Celery beat in production.
    async def _reaper() -> None:
        while True:
            await asyncio.sleep(60)
            await expired_locks.reap_expired_locks()
 
    task = asyncio.create_task(_reaper())
    yield
    task.cancel()


app = FastAPI(
    title="Ticketing API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(venues.router)
app.include_router(events.router)
app.include_router(tiers.router)
app.include_router(inventory.router)
app.include_router(purchase.router)


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {"status": "ok"}