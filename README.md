# FastAPI Task Hub API

A production-ready FastAPI application boilerplate implementing a layered architecture (**Router → Service → Repository → Database**), managed efficiently with **`uv`**.

## 🛠 Tech Stack & Tools

- **Package Manager:** `uv` (`pyproject.toml`)
- **Framework:** FastAPI 0.111+
- **Database ORM:** SQLAlchemy 2.x (Async with `asyncpg`)
- **Database Engine:** PostgreSQL 16 (Hosted on NeonDB)
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

Update `DATABASE_URL` in `.env` with your NeonDB PostgreSQL Connection String:
```env
DATABASE_URL="postgresql+asyncpg://<username>:<password>@<neon-hostname>/<dbname>?sslmode=require"
```

### 3. Run Application Locally
```bash
uv run uvicorn app.main:app --reload
```

---

## 🐳 Running with Docker Compose

```bash
docker-compose up -d --build
```
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
docker-compose exec web alembic revision --autogenerate -m "Initial tables"
```

Apply migrations to NeonDB PostgreSQL:
```bash
# Locally with uv
uv run alembic upgrade head

# Or via Docker Container
docker-compose exec web alembic upgrade head
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

---

## 🔄 Typical Request Flow

```text
Client -> Router (api/v1/endpoints/users.py) -> Service (services/user_service.py) -> Repository (repositories/user_repository.py) -> Database (NeonDB)
```
