# Base image
FROM python:3.12.1-slim-bullseye

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create a non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR //

# Set environment variables
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Copy requirements file
COPY requirements.txt /app/

# Create virtual environment and install dependencies
RUN uv venv $VIRTUAL_ENV && \
    uv pip install --no-cache -r app/requirements.txt

# Copy application code
COPY . .

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
