# AGENTS.md — task-hub-api

## 1. Project Stack

- **Runtime:** Python 3.12+. Use `uv` exclusively for dependency and environment management.
- **Framework:** FastAPI 0.111+ with Uvicorn 0.30+ (ASGI server)
- **Database:** PostgreSQL 16 hosted by Docker Compose, accessed through SQLAlchemy 2.x async (`asyncpg` driver).
- **Migrations:** Alembic 1.13+ with async runner
- **Validation & Settings:** Pydantic v2 + `pydantic-settings` v2 (reads from `.env`)
- **Cache:** Redis 7 hosted by Docker Compose via `redis.asyncio` (connection pool initialized and verified in lifespan)
- **Auth helpers:** `passlib[bcrypt]` for password hashing
- **Linter/Formatter:** Ruff 0.4+ (rules: E, W, F, I, UP — line-length 88, target py312)

---

## 2. Development Commands

```bash
# Install dependencies
uv sync

# Run dev server (reload on file change)
uv run uvicorn app.main:app --reload

# Run via Docker Compose with automatic source sync/rebuild
docker compose watch

# Lint and auto-fix
uv run ruff check --fix app tests --exclude app/db/migrations/versions

# Format
uv run ruff format app tests --exclude app/db/migrations/versions

# Create migration
uv run alembic revision --autogenerate -m "describe change"

# Apply migrations only to an explicitly confirmed target environment
uv run alembic upgrade head
```

---

## 3. Code Style Conventions

### Layered architecture — strict call direction
```
Router (endpoints/) → Service (services/) → Repository (repositories/) → DB
```
Routers **never** call repositories directly. Services should not import peer
domain services by default. Cross-domain workflows belong in a dedicated
application/orchestration service with injected dependencies and an acyclic
dependency graph.

### Raise domain exceptions, never raw HTTPException in services
```python
# CORRECT — in service layer
if not user:
    raise EntityNotFoundError("User", user_id)

# WRONG — HTTPException leaks HTTP concern into business logic
if not user:
    raise HTTPException(status_code=404, detail="Not found")
```

### Pydantic schemas — separate input and output concerns
```python
class UserBase(BaseModel): ...      # shared fields
class UserCreate(UserBase): ...     # input for POST
class UserUpdate(BaseModel): ...    # input for PATCH (all fields Optional)
class UserResponse(UserBase): ...   # output (model_config = from_attributes=True)
```
Use these CRUD names when they fit the feature. Purpose-specific schemas such
as `RegisterRequest` or `AuthUserResponse` are also valid; do not create unused
classes only to satisfy a naming template.

### `model_dump(exclude_unset=True)` for updates

Use `user_in.model_dump(exclude_unset=True)` for PATCH-style updates so omitted
fields are not overwritten.

### Repository flush, not commit

Repositories use `await session.flush()` and refresh objects when needed.
Transaction commit/rollback belongs to the `get_db()` dependency.

### SQLAlchemy models and relationships

- Use SQLAlchemy 2.x `Mapped[...]` and `mapped_column`; do not introduce legacy
  `Column(...)` model declarations.
- Put relationship-only imports behind `if TYPE_CHECKING:` when needed to avoid
  circular runtime imports.

---

## 4. Architecture Constraints

- **Entry point:** `app/main.py` — app factory `create_app()`, lifespan context for startup/shutdown.
- **Settings:** All config lives in `app/core/config.py` (`Settings` via `pydantic-settings`). Never hardcode secrets or URLs inline.
- **DB session:** The `get_db()` async generator in `app/db/session.py` owns commit/rollback. No other layer calls `session.commit()`.
- **Dependency wiring:** Dependency provider/factory functions live in `app/api/dependencies.py`. Endpoints may declare `Depends(get_*_service)`, but they receive services and never construct or inject repositories or database sessions directly.
- **Models → DB base:** All ORM models inherit from `app.db.base.Base`. The base auto-provides `id` (UUID), `created_at`, `updated_at`.
- **No cross-layer imports:** `app/repositories/` must not import from `app/services/`. `app/models/` must not import from `app/schemas/`.
- **Versioning:** All routes live under `app/api/v1/endpoints/`. New API versions get their own `v2/` directory.

---

## 5. Testing and Runtime Conventions

- New or changed behavior requires corresponding automated tests.
- A bug fix requires a regression test that demonstrates the failure before the
  fix and passes afterward.
- Unit tests must be deterministic and must not require live PostgreSQL, Redis,
  or other external services.
- Database, Redis, network, and file I/O on request paths must not block the
  event loop. Use async APIs or move unavoidable blocking work off the event
  loop; pure computation and small synchronous helpers are allowed.
- New or modified public functions, service methods, and repository methods
  must declare parameter and return types.

---

## 6. Safety and Generated Files

- **`.env`** — Never expose, print, commit, or modify it unless the user explicitly authorizes the action. Application code must access configuration through the `settings` object.
- **`uv.lock`** — Never edit by hand. Regenerate it with `uv add`, `uv sync`, or `uv lock`. A lockfile-only change is allowed when intentional (for example, a dependency refresh) and must be explained.
- **`app/db/migrations/`** — Always review generated Alembic revisions before applying them and adjust autogenerated output when necessary. Never rewrite an already-applied migration; create a corrective revision instead.
- **Shared databases** — Never run `alembic upgrade`, `alembic downgrade`, destructive SQL, or data migrations against a shared, staging, or production database without explicit authorization and confirmation of the target environment. Generating or reviewing a revision does not authorize applying it.
- **`app/db/base.py`** — Do not add entity-specific columns here. `id`, `created_at`, `updated_at` only.
- **`.venv/`, `__pycache__/`, `.ruff_cache/`** — Generated artifacts, never touch.
- **`alembic.ini`** — Do not change `sqlalchemy.url` inline; it is set dynamically by the async runner.

---

## 7. CodeGraph Workflow

When a `.codegraph/` directory exists at the repository root, use CodeGraph
before grep/find or direct file reads to locate or understand code:

```bash
codegraph explore "<symbols, files, or question>"
```

- Prefer the `codegraph_explore` MCP tool when it is available.
- Query named symbols or the end-to-end flow being changed so callers and blast
  radius are visible before editing.
- Use direct reads or `rg` for configuration, documentation, generated files,
  or details CodeGraph does not cover.
- Do not initialize CodeGraph automatically when the repository is not indexed.

---

## 8. Required Verification Before Completion

Verification is proportional to the files and behavior changed:

- **Python application or test code:** run all three commands from the repository root:

```bash
uv run ruff check app tests --exclude app/db/migrations/versions
uv run pyright
uv run pytest
```

- **Documentation-only changes:** inspect the final diff and run
  `git diff --check`; Python checks are not required unless the documentation
  change also modifies executable examples or project behavior.
- **ORM model or migration changes:** run the Python checks above, review the
  generated revision, and run `uv run alembic check` when the configured
  database is available. Report clearly when the database check cannot run.
- **Dependency changes:** regenerate `uv.lock` with `uv` and run the Python
  checks above.

- Required checks must exit successfully before the agent reports completion.
- Agents must fix verification failures introduced by their changes.
- Do not use `--fix` for final verification because verification must not modify
  source files.
- If a failure is demonstrably pre-existing and outside the task scope, report
  the exact command, file, and error instead of claiming all checks passed.
- Generated Alembic revisions are excluded from Ruff; they still require manual
  review before application.

---

## 9. Git Workflow

- **Branch naming:** `feature/<name>`, `fix/<name>`, `chore/<name>` (e.g. `feature/auth-jwt`, `fix/user-email-unique`)
- **Commit format:** Conventional Commits — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:` (e.g. `feat: add workspace member endpoint`)
- **Merge strategy:** Squash merge PRs into `main`. Keep commit history linear.
- **Never commit:** `.env` or secrets. Commit `uv.lock` only when its change is intentional and produced by `uv`.
