from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text

from backend.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 Startup logic
    print("Starting up...")

    # (Optional) test DB connection
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield

    # 🔹 Shutdown logic
    print("Shutting down...")


app = FastAPI(
    title="Flash Sale API",
    lifespan=lifespan
)


@app.get("/")
async def root():
    return {"message": "API running 🚀"}