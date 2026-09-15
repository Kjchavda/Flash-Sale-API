from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

try:
    from app.database import Base, engine
    from app.routers import auth
except ImportError:
    from .database import Base, engine
    from .routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # 1. Startup: Ensure 'auth' schema exists and initialize tables
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth;"))
        await conn.run_sync(Base.metadata.create_all)
    print("[system] Auth service database tables initialized.")

    yield

    # 2. Shutdown: Dispose engine connections
    await engine.dispose()
    print("[system] Auth service database engine disposed.")


app = FastAPI(
    title="Auth Service API",
    version="0.1.0",
    description="Authentication and User Management Microservice for Flash Sale API",
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

# Include routers - mounted at /auth and at root for flexibility
app.include_router(auth.router, prefix="/auth")



@app.get("/health", tags=["Meta"])
async def health() -> dict:
    status = {"status": "ok", "service": "auth-service", "database": "unknown"}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["database"] = "ok"
    except Exception as e:
        status["database"] = f"error: {e}"
        status["status"] = "error"

    return status
