from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from app.routers import notify
    from app.middleware.logging_middleware import LoggingMiddleware
except ImportError:
    from .routers import notify
    from .middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    print("[system] Notification service started.")
    yield
    print("[system] Notification service shut down gracefully.")


app = FastAPI(
    title="Notification Service API",
    version="0.1.0",
    description="Notification Microservice for Flash Sale API (Booking confirmation dummy logger)",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

# Include notification router
app.include_router(notify.router, prefix="/notify")
app.include_router(notify.router)  # Also available without prefix (e.g., /booking-confirmation)


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {
        "status": "ok",
        "service": "notification-service",
    }
