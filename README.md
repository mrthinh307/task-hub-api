# FastAPI - Taskhub

A production-ready FastAPI application boilerplate implementing a layered architecture (**Router → Service → Repository → Database**), managed efficiently with **`uv`**.

## 🛠 Tech Stack & Tools

- **Package Manager:** `uv` (`pyproject.toml`)
- **Framework:** FastAPI 0.111+
- **Database ORM:** SQLAlchemy 2.x (Async with `asyncpg`)
- **Database Engine:** PostgreSQL 16 (Hosted locally by Docker Compose)
- **Migrations:** Alembic (Async runner)
- **Data Validation & Settings:** Pydantic v2 & `pydantic-settings`
- **Cache & Session:** Redis 7 (`redis.asyncio`)
- **Containerization:** Docker & Docker Compose
- **Linter & Formatter:** Ruff

---

## 📁 Folder Structure

```text
app/
├── api/
│   ├── dependencies.py          # FastAPI Depends (Service & Repository Injection)
│   └── v1/
│       ├── api.py               # API v1 router aggregator
│       └── endpoints/           # HTTP endpoints (routers)
│           ├── users.py
│           └── products.py
│
├── core/
│   ├── config.py                # Pydantic BaseSettings (.env configuration)
│   ├── security.py              # Password hashing & security helpers
│   ├── logging.py               # Global logger setup
│   └── exceptions.py            # Custom HTTP exception handlers
│
├── db/
│   ├── base.py                  # SQLAlchemy 2.x DeclarativeBase
│   ├── session.py               # Async Engine, AsyncSessionLocal & Redis client
│   └── migrations/              # Alembic async migration environment & revisions
│
├── models/                      # SQLAlchemy ORM Models
│   ├── user.py
│   ├── product.py
│   └── order.py
│
├── schemas/                     # Pydantic Request / Response Schemas
│   ├── user.py
│   ├── product.py
│   └── order.py
│
├── repositories/                # Database Access Layer (Queries)
│   ├── base_repository.py       # Generic Async CRUD BaseRepository
│   ├── user_repository.py
│   └── product_repository.py
│
├── services/                    # Business Logic Layer
│   ├── user_service.py
│   └── product_service.py
│
├── utils/                       # Utility Helpers & Custom Validators
│   ├── helpers.py
│   └── validators.py
│
├── static/
├── templates/
├── main.py                      # Application Entry Point with Lifespan
└── __init__.py
```

---

## 🚀 Quickstart Guide with `uv`

### 1. Setup Virtual Environment & Install Dependencies
```bash
# Create virtualenv and sync dependencies from pyproject.toml
uv sync
```

### 2. Configure Environment Variables
Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

Configure `.env` to connect local commands to the PostgreSQL port exposed by
Docker Compose:
```env
DATABASE_URL="postgresql+asyncpg://task_hub:task_hub_dev_password@localhost:5432/task_hub"
```

```bash
docker compose up -d --wait postgres redis
uv run alembic upgrade head
```

### 3. Run the Application Locally

Start PostgreSQL and Redis with Docker Compose:

```bash
docker compose up -d --wait postgres redis
```

Apply the database migrations:

```bash
uv run alembic upgrade head
```

Then start the FastAPI development server on your host machine:

```bash
uv run uvicorn app.main:app --reload
```

When the API runs locally, it connects to PostgreSQL and Redis through the ports
exposed on `localhost`. Make sure the local values in `.env` use hosts such as:

```env
DATABASE_URL=postgresql+asyncpg://task_hub:task_hub_dev_password@localhost:5432/task_hub
REDIS_URL=redis://localhost:6379/0
```

---

## 🐳 Running with Docker Compose

Start the complete development environment with Compose Watch:

```bash
docker compose up --watch
```

This command starts the following services:

* `api`: FastAPI application
* `postgres`: PostgreSQL database
* `redis`: Redis server

The `api` service waits until PostgreSQL and Redis pass their health checks
before starting.

Compose Watch applies the rules defined under `develop.watch`:

* Changes under `app/` are synchronized into `/app/app` inside the running API
  container.
* Changes to `pyproject.toml`, `uv.lock`, or `Dockerfile` rebuild the API image
  and recreate the API container.

The API process inside the container must run Uvicorn with `--reload` for
synchronized Python source changes to reload the application automatically.
Otherwise, use the `sync+restart` Watch action instead of `sync`.

Inside the Compose network, the API connects to the other services using their
service names:

```text
postgres:5432
redis:6379
```

From the host machine, PostgreSQL and Redis are available through their exposed
ports on `localhost`.

### Apply database migrations

On the first startup, and whenever new Alembic migrations are added, run:

```bash
docker compose exec api alembic upgrade head
```

### Application URLs

The API is available at:

```text
http://localhost:8000
```

API documentation:

* Swagger UI: `http://localhost:8000/docs`
* ReDoc: `http://localhost:8000/redoc`

### Data persistence

PostgreSQL stores its data in the `postgres_data` named volume.

Redis uses append-only persistence and stores its data in the `redis_data`
named volume.

The volumes are preserved when containers are rebuilt, recreated, or stopped
with:

```bash
docker compose down
```

To stop the services and permanently delete both PostgreSQL and Redis data, run:

```bash
docker compose down -v
```

> **Warning:** `docker compose down -v` permanently removes the
> `postgres_data` and `redis_data` volumes.

To start the services again later:

```bash
docker compose up --watch
```

---

## 🧹 Code Quality & Linting with Ruff

Run linter and auto-fix issues:
```bash
uvx ruff check --fix .
```

Format codebase:
```bash
uvx ruff format .
```

Run check-type:
```bash
uv run pyright
```

---

## 🔄 Typical Request Flow

```text
Client -> Router (api/v1/endpoints/users.py) -> Service (services/user_service.py) -> Repository (repositories/user_repository.py) -> Database (PostgreSQL in Docker)
```
