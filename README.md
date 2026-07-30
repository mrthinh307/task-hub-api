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

### 3. Run Application Locally
```bash
uv run uvicorn app.main:app --reload
```

---

## 🐳 Running with Docker Compose

```bash
docker compose watch
```
Compose Watch syncs changes under `app/` into the running container. Changes to
`pyproject.toml`, `uv.lock`, or `Dockerfile` rebuild the API image automatically.
PostgreSQL runs in the `postgres` service and Redis runs in the `redis` service.
The API uses their internal Compose hostnames while it runs in Docker. Local
commands connect through the ports exposed on `localhost`.

On the first startup, apply the database migrations:

```bash
docker compose exec api alembic upgrade head
```

PostgreSQL stores its database files in the `postgres_data` named volume.
Rebuilding or recreating containers, and running `docker compose down`, preserve
this volume. Running `docker compose down -v` explicitly deletes it and all
database data stored in it.

Redis has append-only persistence enabled and stores its files in the
`redis_data` named volume. The same volume lifecycle rules apply: normal
container recreation preserves it, while `docker compose down -v` deletes it.

The API server will be available at: `http://localhost:8000`
- Interactive OpenAPI Docs (Swagger): `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 🔄 Database Migrations with Alembic

Create a new migration revision:
```bash
# Locally with uv
uv run alembic revision --autogenerate -m "Initial tables"

# Or via Docker Container
docker compose exec api alembic revision --autogenerate -m "Initial tables"
```

Apply migrations to Docker-hosted PostgreSQL:
```bash
# Locally with uv
uv run alembic upgrade head

# Or via Docker Container
docker compose exec api alembic upgrade head
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
