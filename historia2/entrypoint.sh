#!/bin/sh
# entrypoint.sh
# ─────────────────────────────────────────────────────────────────────────────
# Historia 2 — entrypoint del contenedor.
#
# Secuencia:
#   1. Espera a que Postgres acepte conexiones (evita el race condition
#      clásico donde la app arranca antes que la BD).
#   2. Corre las migraciones de Alembic (idempotente: si ya están aplicadas
#      no hace nada).
#   3. Levanta uvicorn.
#
# Variables de entorno requeridas:
#   DATABASE_URL   — URL de conexión a Postgres
#   PORT           — puerto donde escucha uvicorn (default 8002)
# ─────────────────────────────────────────────────────────────────────────────

set -e

PORT="${PORT:-8002}"

# ── 1. Esperar a Postgres ─────────────────────────────────────────────────────
# Extrae host y puerto de DATABASE_URL para usarlos en el health-check.
# Formato esperado: postgresql://user:pass@host:5432/dbname
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

    # ── 2. Migraciones ───────────────────────────────────────────────────────
    echo "Running Alembic migrations..."
    alembic upgrade head
    echo "Migrations complete."
fi

# ── 3. Arrancar uvicorn ───────────────────────────────────────────────────────
echo "Starting uvicorn on 0.0.0.0:$PORT ..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1
