ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION:-3.13}-slim-bookworm AS builder

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Copy dependency files for installation
COPY backend/pyproject.toml backend/uv.lock /app/

# Create virtual environment and install dependencies using uv sync
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Runtime stage
FROM python:${PYTHON_VERSION:-3.13}-slim-bookworm

# Install uv (needed for uv run commands)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
RUN useradd -m appuser

WORKDIR /app

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Copy installed virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy backend application code
COPY backend/ /app/

# Copy changelog to project root
COPY CHANGELOG.md /CHANGELOG.md

RUN chown -R appuser:appuser /app
USER appuser

# Command to run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
