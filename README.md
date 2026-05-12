# Flash Sale API: High-Concurrency Ticketing Engine
[![Live Deployment](https://img.shields.io/badge/Live_Deployment-Available_Now-success?style=for-the-badge)](https://ai-listing-rho.vercel.app/)
[![Watch Demo](https://img.shields.io/badge/Demo-View_GIF_Below-blue?style=for-the-badge)](#-gallery)

A high-performance, distributed backend system engineered to handle massive, instantaneous user traffic during flash sales. This API prevents race conditions, eliminates double-booking, and survives database connection floods using row-level locking, transaction pooling, and distributed caching.

---

# 🚀 Architectural Highlights

## Concurrency & Data Integrity
Implemented mathematical deadlock prevention and row-level `FOR UPDATE SKIP LOCKED` logic in PostgreSQL to safely handle concurrent ticket locking without double-booking inventory.

## Connection Pool Management
Designed a dual-URL database architecture utilizing PgBouncer (Transaction Pooling) to survive connection tsunamis during synthetic load tests, while routing Alembic DDL migrations through isolated direct connections to prevent lock contention.

## Self-Healing Infrastructure
Built an asynchronous background worker using APScheduler to continuously sweep the database and release orphaned ticket locks (10-minute TTL) from abandoned checkout sessions, maximizing inventory utilization.

## Edge Security & Anti-Bot
Developed a custom, distributed sliding-window rate limiter backed by Redis to instantly throttle malicious bot traffic and mitigate DDoS attempts at the application edge.

---

# 🛠 Tech Stack

## Languages & Databases

- Python 3.13
- PostgreSQL (Neon Serverless)
- Redis (Upstash Serverless)

## Frameworks

- FastAPI

## Libraries

- SQLAlchemy (Asyncio)
- Pydantic
- Alembic
- APScheduler
- Redis-py
- Locust (Load Testing)

---

# 📊 Load Testing & Performance Validation

To demonstrate the engine's capability, the API was stress-tested using synthetic Locust swarms simulating a flash sale traffic spike.

## Test Parameters

- **Concurrent Users:** 100
- **Spawn Rate:** 10 users/sec
- **Target Endpoint:** `POST /tickets/lock`

## Results

- Successfully queued and processed concurrent transactions without a single database crash, `429` connection drop, or double-booked ticket.
- Connection pooling kept active database connections within the strict limits of the serverless provider.

> Add your Locust screenshots below:
>
> - Green success charts
> - 0% failure rate
> - Stable response times

---

# ⚙️ Local Development Setup

## 1. Clone and Install Dependencies

```bash
git clone https://github.com/Kjchavda/Flash-Sale-API.git
cd Flash-Sale-API

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## 2. Environment Variables

Create a `.env` file in the root directory:

```env
# Standard URL routed through PgBouncer for concurrent pooling
DATABASE_URL=postgresql+asyncpg://user:pass@ep-hostname-pooler.region.aws.neon.tech/dbname

# Direct URL for Alembic schema migrations
DIRECT_DATABASE_URL=postgresql+asyncpg://user:pass@ep-hostname.region.aws.neon.tech/dbname

# Upstash Serverless Redis
REDIS_URL=rediss://default:pass@endpoint.upstash.io:6379
```

---

## 3. Run Migrations

Apply the database schema using the direct connection:

```bash
alembic upgrade head
```

---

## 4. Start the Server

Boot the FastAPI application (the background lock-reaper will start automatically):

```bash
uvicorn backend.main:app --reload
```

---

# 📂 Project Structure

```plaintext
├── alembic/                # Database migration scripts
├── backend/
│   ├── main.py             # FastAPI application and lifespan events
│   ├── database.py         # Async engine and connection pooling setup
│   ├── models.py           # SQLAlchemy ORM models
│   ├── dependencies.py     # Redis rate limiter and DB session injectors
│   ├── tasks.py            # APScheduler background workers
│   └── routers/            # Modular API endpoints
├── locustfile.py           # Synthetic load testing scripts
└── users.csv               # Seeded user data for robust testing
```

---

# 🔥 Core Features

- Distributed ticket locking engine
- PostgreSQL row-level locking
- `FOR UPDATE SKIP LOCKED` concurrency control
- Redis-backed sliding-window rate limiter
- Background lock expiration & cleanup
- PgBouncer transaction pooling
- Async FastAPI architecture
- Serverless-ready infrastructure
- Synthetic load-tested reliability

---

# 📈 Future Improvements

- JWT authentication & user sessions
- Kafka/RabbitMQ event-driven order processing
- Real-time ticket availability with WebSockets
- Kubernetes deployment manifests
- Prometheus + Grafana monitoring
- CI/CD pipeline integration
- Multi-region Redis replication

---
