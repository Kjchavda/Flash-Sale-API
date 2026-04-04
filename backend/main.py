from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from backend.database import Base, engine
from backend.routers import events, inventory, tiers, venues


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Create all tables on startup (swap for Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Ticketing API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(venues.router)
app.include_router(events.router)
app.include_router(tiers.router)
app.include_router(inventory.router)


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {"status": "ok"}