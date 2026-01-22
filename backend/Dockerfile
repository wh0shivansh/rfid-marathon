# RFID Marathon Management System - Backend Dockerfile
# Security Level: Production, SSL-enforced

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System dependencies for psycopg2 and cryptography
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (better caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Non-root user for runtime hardening
RUN useradd -ms /bin/bash appuser
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Healthcheck (basic HTTP check)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

# Entry point: run migrations then start server
CMD ["sh", "-c", "python -c 'from database.migrations import run_migrations; run_migrations()' && uvicorn main:app --host 0.0.0.0 --port ${SERVER_PORT:-8000}"]
