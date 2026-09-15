import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

load_dotenv()

# 1. Update URL: Ensure it starts with postgresql+asyncpg://
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 2. Create Async Engine
engine = create_async_engine(
    DATABASE_URL, # Keep your existing URL variable here
    pool_size=20,          # The baseline number of open connections to maintain
    max_overflow=30,       # Allow 30 extra connections during massive spikes
    pool_timeout=30,       # If Locust asks for a 51st connection, make it wait in line up to 30s instead of crashing
    pool_recycle=1800,     # Refresh connections every 30 minutes to prevent Neon from auto-dropping stale ones
    echo=False             # Ensure this is False to save terminal I/O speed
)

# 3. Use async_sessionmaker
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    autocommit=False, 
    autoflush=False, 
    expire_on_commit=False,
    class_=AsyncSession
)

# 4. Updated Dependency for FastAPI
async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()