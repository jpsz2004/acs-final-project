# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
# Historia 5 — WebSockets + EventBus + JWT + PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN adduser --disabled-password --gecos "" appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# appuser must own /app so pytest can write .pytest_cache
RUN chown -R appuser:appuser /app

USER appuser

# Historia 5 runs on port 8005
EXPOSE 8005

ENTRYPOINT ["/entrypoint.sh"]
