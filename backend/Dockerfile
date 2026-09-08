ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION:-3.13}-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app

# Cache runtime dependencies separately from the editable application and its CLI.
COPY backend/pyproject.toml backend/uv.lock /app/
RUN uv sync --frozen --no-default-groups --no-install-project --no-cache
COPY backend/ /app/
RUN uv sync --frozen --no-default-groups --no-cache

FROM python:${PYTHON_VERSION:-3.13}-slim-bookworm
COPY --from=builder /bin/uv /bin/uv
RUN useradd --create-home --uid 1000 appuser \
    && install -d -o appuser -g appuser /var/log/fallout_shelter
WORKDIR /app

# API, worker, migration, and CLI commands use the baked environment.
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    UV_NO_SYNC=1 \
    UV_NO_CACHE=1 \
    UV_NO_DEFAULT_GROUPS=1
COPY --from=builder --chown=appuser:appuser /app /app
COPY CHANGELOG.md /CHANGELOG.md
USER appuser

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
