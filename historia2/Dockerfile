# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Historia 2 — Producer/Consumer  (FastAPI + PostgreSQL + Workers)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Usuario sin privilegios.
RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app

# Dependencias compiladas desde el builder.
COPY --from=builder /install /usr/local

# Código fuente.
COPY . .

# Entrypoint: espera Postgres → migraciones → uvicorn.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Transfiere la propiedad de /app a appuser ANTES de cambiar de usuario.
# Sin esto pytest no puede escribir su cache en /app/.pytest_cache.
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8002

ENTRYPOINT ["/entrypoint.sh"]
