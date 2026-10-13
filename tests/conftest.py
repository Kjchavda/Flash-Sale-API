import asyncio
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# 1. Load test environment variables BEFORE importing the app
root_dir = Path(__file__).resolve().parent.parent
test_env_path = root_dir / ".env.test"

load_dotenv(test_env_path, override=False)

# Ensure SECRET_KEY is non-empty
if not os.getenv("SECRET_KEY"):
    os.environ["SECRET_KEY"] = (
        "test-secret-key-for-flash-sale-tests-1234567890"
    )

# Configure sys.path before importing application modules
ticket_service_dir = root_dir / "ticket_service"

for p in [str(root_dir), str(ticket_service_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Alias ticket_service.app to 'app' if needed
import ticket_service.app as ts_app

if "app" not in sys.modules:
    sys.modules["app"] = ts_app

# Now import pytest and application modules
import pytest
from jose import jwt
from fastapi.testclient import TestClient

from ticket_service.app.main import app
from ticket_service.app.database import Base, get_db
from ticket_service.app.middleware.auth_middleware import (
    SECRET_KEY,
    ALGORITHM,
    get_current_user,
)

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.pool import NullPool

from ticket_service.app.models import (
    Venue,
    Event,
    TicketTier,
    Ticket,
    Order,
    OrderItem,
)
from contextlib import asynccontextmanager

# 3. Configure Database Engine for Testing (AsyncPG)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/flashsale_test")
ASYNC_DATABASE_URL = DATABASE_URL
if ASYNC_DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

from sqlalchemy.pool import NullPool

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

_db_available = False

# 4. Session Fixture to Create / Drop Schema
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    global _db_available
    async def _init_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _drop_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    try:
        asyncio.run(_init_db())
        _db_available = True
    except Exception as exc:
        _db_available = False
        print(f"\n[setup_database] Notice: Unable to connect to test Postgres: {exc}")
        print("[setup_database] Note: In local dev, change 'yourpassword' in .env.test to your local Postgres password. In CI, Postgres service is used automatically.")

    yield _db_available

    if _db_available:
        try:
            asyncio.run(_drop_db())
        except Exception:
            pass


# 5. Database Session Fixture (Per-Test)
@pytest.fixture
async def db_session():
    if not _db_available:
        pytest.skip("PostgreSQL test database not accessible. Update .env.test with your local Postgres password, or run via CI.")
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()



from contextlib import asynccontextmanager

@asynccontextmanager
async def _noop_lifespan(app):
    yield

app.router.lifespan_context = _noop_lifespan


# 6. FastAPI TestClient Fixture with DB Dependency Override
@pytest.fixture
def client():
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# 7. Helper Fixture for Generating Valid JWT Auth Headers
@pytest.fixture
def auth_headers():
    from ticket_service.app.middleware.auth_middleware import SECRET_KEY, ALGORITHM
    def _make_headers(user_id=None, email="testuser@example.com"):
        uid = str(user_id or uuid.uuid4())
        token = jwt.encode({"sub": uid, "email": email}, SECRET_KEY, algorithm=ALGORITHM)
        return {"Authorization": f"Bearer {token}"}, uuid.UUID(uid)
    return _make_headers


# 8. Notification Service TestClient Fixture
@pytest.fixture
def notif_client():
    try:
        from notification_service.app.main import app as notif_app
        with TestClient(notif_app) as tc:
            yield tc
    except Exception:
        yield None
