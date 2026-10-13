# Flash Sale API: Event-Driven Ticketing Microservices

[![Live Deployment](https://img.shields.io/badge/Live_on-AWS_EC2-success?style=for-the-badge&logo=amazonaws)](http://YOUR-EC2-PUBLIC-IP-OR-DOMAIN/tickets/docs)
[![Watch Demo](https://img.shields.io/badge/Demo-View_GIF_Below-blue?style=for-the-badge)](#-gallery)

<!-- TODO: replace YOUR-EC2-PUBLIC-IP-OR-DOMAIN in the badge above with your real EC2 public IP / domain. -->

A high-performance, distributed backend system engineered to handle massive, instantaneous user traffic during flash sales. The platform is split into independently deployable **auth**, **ticket**, and **notification** microservices behind an **Nginx** gateway, communicating asynchronously over **Apache Kafka**. It prevents race conditions, eliminates double-booking, and survives database connection floods using row-level locking, transaction pooling, Redis-backed rate limiting, and distributed caching.

---

# ☁️ Deployment

The full stack is deployed and running on **AWS EC2** using Docker Compose, with the same `docker-compose.yml` used for local development.

- **Single public entry point:** only the Nginx gateway publishes a port (80). The auth, ticket, and notification services and the Kafka broker are reachable only inside the Docker network.
- **Managed data layer:** PostgreSQL (Neon) and Redis (Upstash) stay external cloud services; the EC2 instance connects out to them using the per-service `.env` files.
- **Self-contained messaging:** Kafka runs on the instance in KRaft mode with a persistent `kafka_data` volume.
- **Restart resilience:** every container uses `restart: unless-stopped`, so the stack recovers after a reboot or crash.

Live API docs: `http://YOUR-EC2-PUBLIC-IP-OR-DOMAIN/tickets/docs`

<!-- VERIFY: add the EC2 instance type, whether HTTPS/a domain/Elastic IP is configured, and the security-group rules if you want them documented. -->

### Deploying to EC2

```bash
# On the EC2 instance (Docker + Docker Compose installed)
git clone https://github.com/Kjchavda/Flash-Sale-API.git
cd Flash-Sale-API

# Create ticket_service/.env and auth-service/.env with production values
docker compose up -d --build
```

Make sure the instance's security group allows inbound HTTP (port 80) and SSH from your IP only.

---

# 🚀 Architectural Highlights

## Microservice Architecture
Each service is a standalone FastAPI app with its own Dockerfile, dependencies, and middleware:

| Service | Internal Port | Gateway Route | Responsibility |
| --- | --- | --- | --- |
| `auth-service` | 8001 | `/auth/` | User registration, authentication, and JWT issuance |
| `ticket-service` | 8000 | `/tickets/` | Ticket inventory, locking, bookings, and Kafka event publishing |
| `notification-service` | 8002 | `/notifications/` | Consumes Kafka events and dispatches notifications |

An **Nginx** reverse proxy is the single public entry point (port 80). It routes `/auth/`, `/tickets/`, and `/notifications/` to the matching service over the internal Docker network, and exposes a plain-text gateway health check at `/`.

`auth-service` and `ticket-service` each own their own database schema and Alembic migrations; `notification-service` is stateless and driven entirely by events.

## Event-Driven Communication
`ticket-service` publishes booking events through a Kafka producer (`kafka_producer.py`), and `notification-service` consumes them in a dedicated consumer (`consumer.py`). The broker is a single-node Apache Kafka in **KRaft mode** (no ZooKeeper) using `aiokafka`. Services wait for the broker's health check before starting, keeping notification work off the request path.

<!-- VERIFY: list the Kafka topic names and event payloads. -->

## Authentication & Security
Authentication lives in a dedicated service using **JWT** tokens (`python-jose`) with **bcrypt** password hashing (`passlib`); token and password helpers are in `auth_utils.py`.

<!-- VERIFY: describe how ticket-service validates the JWT (shared secret in dependencies.py?). -->

## Concurrency & Data Integrity
Implemented mathematical deadlock prevention and row-level `FOR UPDATE SKIP LOCKED` logic in PostgreSQL to safely handle concurrent ticket locking without double-booking inventory.

## Self-Healing Infrastructure
Built an asynchronous background worker using APScheduler (`ticket_service/app/tasks/`) to continuously sweep the database and release orphaned ticket locks (10-minute TTL) from abandoned checkout sessions, maximizing inventory utilization.

## Edge Security & Anti-Bot
A distributed, Redis-backed **sliding-window rate limiter**, implemented as FastAPI middleware, throttles malicious bot traffic and mitigates DDoS attempts at the application edge. Limits are shared across instances because counters live in Redis, and the behaviour is covered by automated tests (`tests/test_rate_limit.py`).

<!-- VERIFY: state the actual limits (requests/window), which services/endpoints are covered, and whether it is the custom limiter, SlowAPI, or both. -->

## Testing & Observability
- **Automated tests** with `pytest` and `pytest-asyncio` in `tests/`, covering bookings (`test_bookings.py`), notifications (`test_notif.py`), and rate limiting (`test_rate_limit.py`).
- **Load testing** with Locust (`ticket_service/app/locustfile.py`) simulating flash-sale traffic spikes.
- **Sentry** (`sentry-sdk`) for error tracking.
- **CI** workflows under `.github/`.

<!-- VERIFY: confirm Sentry is initialised, and describe what the .github workflow runs. -->

---

# 🛠 Tech Stack

## Databases & Messaging

- PostgreSQL (Neon Serverless) with PgBouncer transaction pooling
- Redis (Upstash Serverless)
- Apache Kafka (Confluent `cp-kafka` 7.5.0, KRaft mode)

## Frameworks

- FastAPI
- Uvicorn

## Infrastructure

- AWS EC2 (production hosting)
- Docker & Docker Compose
- Nginx (API gateway / reverse proxy)

## Libraries

- SQLAlchemy (Asyncio) + asyncpg
- Pydantic
- Alembic
- APScheduler
- aiokafka
- redis-py
- python-jose (JWT) / passlib + bcrypt
- Sentry SDK
- pytest / pytest-asyncio
- Locust (Load Testing)

---

# 📊 Load Testing & Performance Validation

The ticket service is stress-tested with synthetic Locust swarms simulating a flash-sale traffic spike. The Locust scenarios live in `ticket_service/app/locustfile.py` and authenticate using the seeded accounts in `users_db.csv`.

## Running the Load Test

With the stack running (`docker compose up --build`):

```bash
locust -f ticket_service/app/locustfile.py --host http://localhost
```

Then open `http://localhost:8089`, set the number of users and spawn rate, and start the swarm.

## Test Parameters

- **Concurrent Users:** 100
- **Spawn Rate:** 10 users/sec
- **Target Endpoint:** `POST /tickets/lock`

## Results

- Successfully queued and processed concurrent transactions without a single database crash, `429` connection drop, or double-booked ticket.
- Connection pooling kept active database connections within the strict limits of the serverless provider.
- The rate limiter throttles abusive clients while legitimate traffic continues to be served.

<!-- VERIFY: re-run the test after rewriting the locustfile and rate limiter, then update the figures above and the gallery assets. Adjust the endpoint path if it changes. -->

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

## Run the Full Stack with Docker (Recommended)

**1. Clone the repository**

```bash
git clone https://github.com/Kjchavda/Flash-Sale-API.git
cd Flash-Sale-API
```

**2. Create the per-service `.env` files**

`ticket_service/.env`

```env
# Standard URL routed through PgBouncer for concurrent pooling
DATABASE_URL=postgresql+asyncpg://user:pass@ep-hostname-pooler.region.aws.neon.tech/dbname

# Direct URL for Alembic schema migrations
DIRECT_DATABASE_URL=postgresql+asyncpg://user:pass@ep-hostname.region.aws.neon.tech/dbname

# Upstash Serverless Redis
REDIS_URL=rediss://default:pass@endpoint.upstash.io:6379
```

`auth-service/.env`

```env
# Database connection and JWT signing settings for the auth service
```

<!-- VERIFY: fill in exact variable names for both .env files (DB URLs, JWT secret/algorithm/expiry, Sentry DSN). The notification service reads no .env file in docker-compose.yml. -->

`KAFKA_BOOTSTRAP_SERVERS` is injected by Docker Compose (`kafka:9092`) for the ticket and notification services.

**3. Run migrations**

Each database-backed service has its own Alembic setup. Apply the schema using the direct connection:

```bash
cd ticket_service && alembic upgrade head && cd ..
cd auth-service && alembic upgrade head && cd ..
```

**4. Build and start everything**

```bash
docker compose up --build
```

**5. Open the API**

Everything is served through the gateway on port 80:

| URL | Description |
| --- | --- |
| `http://localhost/` | Gateway health check |
| `http://localhost/auth/docs` | Auth service Swagger UI |
| `http://localhost/tickets/docs` | Ticket service Swagger UI |
| `http://localhost/notifications/docs` | Notification service Swagger UI |

<!-- VERIFY: the Swagger pages behind a path-stripping proxy may fail to load /openapi.json unless root_path is configured. Check these URLs work. -->

Postgres (Neon) and Redis (Upstash) are managed cloud services, so they aren't containerized. Kafka runs in the compose stack with a persistent `kafka_data` volume.

## Running the Tests

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
pytest
```

Test settings live in `pytest.ini` and `.env.test`.

<!-- VERIFY: there is also a second docker-compose file (docker-compose.t...). If it is a test stack, document how to run it here. -->

---

# 📂 Project Structure

```plaintext
├── .github/                      # CI workflows
├── assets/                       # Load-test results and ER diagram
├── auth-service/
│   ├── alembic/                  # Auth DB migrations
│   ├── app/
│   │   ├── middleware/
│   │   ├── routers/
│   │   ├── auth_utils.py         # JWT and password hashing helpers
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── alembic.ini
│   ├── Dockerfile.auth
│   └── requirements.txt
├── ticket_service/
│   ├── alembic/                  # Ticket DB migrations
│   ├── app/
│   │   ├── middleware/           # Redis sliding-window rate limiter
│   │   ├── routers/              # Ticket and booking endpoints
│   │   ├── tasks/                # APScheduler lock-reaper
│   │   ├── database.py
│   │   ├── dependencies.py
│   │   ├── kafka_producer.py     # Publishes booking events
│   │   ├── locustfile.py         # Load testing scenarios
│   │   ├── main.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── alembic.ini
│   ├── Dockerfile.api
│   └── requirements.txt
├── notification_service/
│   ├── app/
│   │   ├── middleware/
│   │   ├── routers/
│   │   ├── consumer.py           # Kafka event consumer
│   │   ├── main.py
│   │   └── schemas.py
│   ├── Dockerfile.notif
│   └── requirements.txt
├── nginx/
│   └── nginx.conf                # Gateway routing
├── tests/
│   ├── conftest.py
│   ├── test_bookings.py
│   ├── test_notif.py
│   └── test_rate_limit.py
├── docker-compose.yml            # Services, Kafka (KRaft), Nginx
├── pytest.ini
├── requirements.txt
└── users_db.csv                  # Seeded users for testing and load tests
```

---

# Database Schema
![ER Diagram](assets/flash-sale-api.svg)

---

# 🔥 Core Features

- Microservice architecture (auth, ticket, notification) behind an Nginx gateway
- Event-driven notifications via Apache Kafka (KRaft mode, `aiokafka`)
- JWT authentication with bcrypt password hashing
- Distributed ticket locking engine
- PostgreSQL row-level locking
- `FOR UPDATE SKIP LOCKED` concurrency control
- Redis-backed sliding-window rate limiter (middleware)
- Background lock expiration & cleanup
- PgBouncer transaction pooling
- Async FastAPI architecture
- Per-service database migrations with Alembic
- Single-command Docker Compose deployment with health-checked dependencies
- Deployed on AWS EC2 behind the Nginx gateway
- Automated test suite (pytest) and CI
- Locust load testing
- Error tracking with Sentry

---

# 📈 Future Improvements

- Real-time ticket availability with WebSockets
- Kubernetes deployment manifests
- Prometheus + Grafana monitoring
- Multi-region Redis replication
- Multi-broker Kafka cluster for high availability

---