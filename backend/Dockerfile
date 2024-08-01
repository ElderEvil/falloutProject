# Base image
FROM python:3.12-slim-bullseye AS build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set working directory
WORKDIR /code

# Set environment variables
ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN uv venv /opt/venv && \
    uv pip install --no-cache -r requirements.txt

# App image
FROM python:3.12-slim-bullseye

# Create a non-root user
RUN useradd -m appuser

# Set working directory
WORKDIR /code

# Copy virtual environment from build stage
COPY --from=build /opt/venv /opt/venv

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Change ownership of application code
RUN chown -R appuser:appuser /code

# Switch to non-root user
USER appuser

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
