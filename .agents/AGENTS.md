# AGENTS.md — task-hub-api

## 1. Project Stack

- **Runtime:** Python 3.11+, managed with `uv` (NOT pip, NOT poetry)
- **Framework:** FastAPI 0.111+ with Uvicorn 0.30+ (ASGI server)
- **Database:** PostgreSQL 16 (NeonDB, cloud-hosted) via SQLAlchemy 2.x async (`asyncpg` driver)
- **Migrations:** Alembic 1.13+ with async runner
- **Validation & Settings:** Pydantic v2 + `pydantic-settings` v2 (reads from `.env`)
- **Cache:** Redis 7 via `redis.asyncio` (connection pool initialized in lifespan)
- **Auth helpers:** `passlib[bcrypt]` for password hashing
- **Linter/Formatter:** Ruff 0.4+ (rules: E, W, F, I, UP — line-length 88, target py312)

---

## 2. Build & Test Commands

```bash
# Install dependencies
uv sync

# Run dev server (reload on file change)
uv run uvicorn app.main:app --reload

# Run via Docker Compose
docker-compose up -d --build

# Lint and auto-fix
uvx ruff check --fix .

# Format
uvx ruff format .

# Create migration
uv run alembic revision --autogenerate -m "describe change"

# Apply migrations
uv run alembic upgrade head

# Manual testing: hit http://localhost:8000/docs (Swagger UI)
# No automated test suite yet — pytest + httpx are installed in [dev] group
```

---

## 3. Code Style Conventions

### Layered architecture — strict call direction
```
Router (endpoints/) → Service (services/) → Repository (repositories/) → DB
```
Routers **never** call repositories directly. Services **never** import other services.

### Async everywhere
```python
# CORRECT — all DB/Redis calls are async
async def get_user_by_id(self, user_id: UUID) -> User:
    user = await self.repo.get_by_id(user_id)
    ...

# WRONG — blocking call inside async function
def get_user_by_id(self, user_id: UUID) -> User:
    ...
```

### Raise domain exceptions, never raw HTTPException in services
```python
# CORRECT — in service layer
if not user:
    raise EntityNotFoundException("User", user_id)

# WRONG — HTTPException leaks HTTP concern into business logic
if not user:
    raise HTTPException(status_code=404, detail="Not found")
```

### Pydantic schema naming — three distinct classes per entity
```python
class UserBase(BaseModel): ...      # shared fields
class UserCreate(UserBase): ...     # input for POST
class UserUpdate(BaseModel): ...    # input for PATCH (all fields Optional)
class UserResponse(UserBase): ...   # output (model_config = from_attributes=True)
```

### `model_dump(exclude_unset=True)` for updates
```python
# CORRECT — only update fields the client actually sent
update_data = user_in.model_dump(exclude_unset=True)

# WRONG — overwrites all fields, including None for omitted ones
update_data = user_in.model_dump()
```

### Repository flush, not commit
```python
# Repositories use flush() — commit is handled by the get_db() dependency
await self.session.flush()
await self.session.refresh(db_obj)
# Do NOT call session.commit() inside a repository method
```

### SQLAlchemy models — use `Mapped` + `mapped_column` (2.x style)
```python
# CORRECT
email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

# WRONG (1.x legacy style)
email = Column(String(255), unique=True, nullable=False)
```

### TYPE_CHECKING guard for circular relationship imports
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.workspace import Workspace
```

---

## 4. Architecture Constraints

- **Entry point:** `app/main.py` — app factory `create_app()`, lifespan context for startup/shutdown.
- **Settings:** All config lives in `app/core/config.py` (`Settings` via `pydantic-settings`). Never hardcode secrets or URLs inline.
- **DB session:** The `get_db()` async generator in `app/db/session.py` owns commit/rollback. No other layer calls `session.commit()`.
- **Dependency wiring:** All `Depends(...)` declarations live **only** in `app/api/dependencies.py`. Endpoints receive services, never repositories.
- **Models → DB base:** All ORM models inherit from `app.db.base.Base`. The base auto-provides `id` (UUID), `created_at`, `updated_at`.
- **No cross-layer imports:** `app/repositories/` must not import from `app/services/`. `app/models/` must not import from `app/schemas/`.
- **Versioning:** All routes live under `app/api/v1/endpoints/`. New API versions get their own `v2/` directory.

---

## 5. Boundaries — Never Touch

- **`.env`** — Never commit, never read directly. Always access via `settings` object.
- **`uv.lock`** — Never edit by hand. Changes only via `uv add <pkg>` or `uv sync`.
- **`app/db/migrations/`** — Never hand-edit generated Alembic migration files after they have been applied. Create a new revision instead.
- **`app/db/base.py`** — Do not add entity-specific columns here. `id`, `created_at`, `updated_at` only.
- **`.venv/`, `__pycache__/`, `.ruff_cache/`** — Generated artifacts, never touch.
- **`alembic.ini`** — Do not change `sqlalchemy.url` inline; it is set dynamically by the async runner.

---

## 6. Git Workflow

- **Branch naming:** `feature/<name>`, `fix/<name>`, `chore/<name>` (e.g. `feature/auth-jwt`, `fix/user-email-unique`)
- **Commit format:** Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:` (e.g. `feat: add workspace member endpoint`)
- **Merge strategy:** Squash merge PRs into `main`. Keep commit history linear.
- **Never commit:** `.env`, secrets, `uv.lock` changes without a matching `pyproject.toml` change.
