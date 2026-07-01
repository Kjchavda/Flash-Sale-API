# Flash Sale API: High-Concurrency Ticketing Engine
[![Live Deployment](https://img.shields.io/badge/Live_Deployment-Available_Now-success?style=for-the-badge)](https://flash-sale-api-mirq.onrender.com/docs)
[![Watch Demo](https://img.shields.io/badge/Demo-View_GIF_Below-blue?style=for-the-badge)](#-gallery)

A high-performance, distributed backend system engineered to handle massive, instantaneous user traffic during flash sales. This API prevents race conditions, eliminates double-booking, and survives database connection floods using row-level locking, transaction pooling, and distributed caching.

---

# 🚀 Architectural Highlights

## Concurrency & Data Integrity
Implemented mathematical deadlock prevention and row-level `FOR UPDATE SKIP LOCKED` logic in PostgreSQL to safely handle concurrent ticket locking without double-booking inventory.

## Self-Healing Infrastructure
Built an asynchronous background worker using APScheduler to continuously sweep the database and release orphaned ticket locks (10-minute TTL) from abandoned checkout sessions, maximizing inventory utilization.

## Edge Security & Anti-Bot
Developed a custom, distributed sliding-window rate limiter backed by Redis to instantly throttle malicious bot traffic and mitigate DDoS attempts at the application edge.

---

# 🛠 Tech Stack

## Databases

- PostgreSQL (Neon Serverless)
- Redis (Upstash Serverless)

## Frameworks

- FastAPI

## Infrastructure

- Docker

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

## 📸 Gallery

<details>
<summary>Click to view locust charts</summary>
<br>
<img src="assets/locust_charts.gif" alt="locust charts">
</details>

<details>
<summary>Click to view locust results</summary>
<br>
<img src="assets/locust_result_check.gif" alt="locust results GIF">
</details>

<details>
<summary>Click to view locust test results </summary>
<br>
<img src="assets/locust_test_results.png" alt="Test result">
</details>

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

## Alternative: Run with Docker

Skip the venv setup entirely — build and run the whole app in a container.

**1. Set up your `.env` file** (same as above ,Docker reads the same variables)

**2. Build and start the container**

```bash
docker compose up --build
```

**3. Open the API**

Visit `http://localhost:8000/docs` for the Swagger UI.

No local Python install needed. Postgres (Neon) and Redis (Upstash) are managed cloud services, so they aren't containerized; the app connects out to them the same way it does when run locally.

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
├── Dockerfile.api          # Container build definition for the API
├── docker-compose.yml      # Local orchestration (single service)
├── .dockerignore
├── locustfile.py           # Synthetic load testing scripts
└── users.csv               # Seeded user data for robust testing
```

---

# Database Schema
![ER Diagram](assets/flash-sale-api.svg)

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
