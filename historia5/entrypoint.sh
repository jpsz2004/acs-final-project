#!/bin/sh
# entrypoint.sh — Historia 5
# ─────────────────────────────────────────────────────────────────────────────
# 1. Wait for Postgres to accept connections.
# 2. Run Alembic migrations (idempotent).
# 3. Start uvicorn.
# ─────────────────────────────────────────────────────────────────────────────

set -e

PORT="${PORT:-8005}"

if [ -n "$DATABASE_URL" ]; then
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    DB_PORT="${DB_PORT:-5432}"

    echo "Waiting for Postgres at $DB_HOST:$DB_PORT ..."
    until python -c "
import socket, sys
try:
    s = socket.create_connection(('$DB_HOST', $DB_PORT), timeout=2)
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
"; do
        echo "  Postgres not ready — retrying in 2s"
        sleep 2
    done
    echo "Postgres is ready."

    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

echo "Starting uvicorn on 0.0.0.0:$PORT ..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1
