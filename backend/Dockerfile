# Read Python version from .python-version file
ARG PYTHON_VERSION
FROM python:${PYTHON_VERSION:-3.13}-slim-bookworm

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR /app

# Set environment variables
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Copy uv files for dependency installation
COPY pyproject.toml uv.lock /app/

# Create virtual environment and install dependencies using uv sync
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Copy application code
COPY . .

# Command to run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
