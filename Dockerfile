FROM python:3.11-slim

# Install uv from Astral official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency definition files
COPY pyproject.toml .
# COPY uv.lock . # Uncomment when lockfile is generated

# Install dependencies using uv
RUN uv pip install --system .

# Copy remaining project files
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
