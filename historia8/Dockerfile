# syntax=docker/dockerfile:1

# ── Build stage ──────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# No root in production — good practice even for academic projects
RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

USER appuser

# Default: run the simulation. Override with docker-compose for tests.
CMD ["python", "-m", "app.main"]