import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from backend.database import Base, engine
from backend.routers import events, inventory, tiers, venues, purchase

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 1. Startup: Initialize database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
 
    yield 
    
    # 2. Shutdown: Add any necessary cleanup here later (e.g., engine.dispose())

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