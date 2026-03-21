#!/bin/bash
set -e

echo "Running database migrations..."
cd /app/backend 2>/dev/null || cd backend 2>/dev/null || true
alembic upgrade head || echo "Migration warning: alembic upgrade failed (may already be up to date)"

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
