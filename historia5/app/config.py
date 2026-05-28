from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    worker_count: int = int(os.getenv("WORKERS_COUNT", "4"))
    processing_delay_ms: int = int(os.getenv("PROCESSING_DELAY_MS", "50"))
    api_key: str | None = os.getenv("API_KEY")
    queue_maxsize: int = int(os.getenv("QUEUE_MAXSIZE", "0"))
    database_url: str | None = os.getenv("DATABASE_URL")
    jwt_secret: str = os.getenv("JWT_SECRET", "supersecret_jwt_key_please_change_12345")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_seconds: int = int(os.getenv("JWT_EXPIRATION_SECONDS", "3600"))
    public_base_url: str | None = os.getenv("PUBLIC_BASE_URL")
    webhook_max_retries: int = int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
    webhook_backoff_base_ms: int = int(os.getenv("WEBHOOK_BACKOFF_BASE_MS", "200"))
    circuit_breaker_failure_threshold: int = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    circuit_breaker_cooldown_s: int = int(os.getenv("CB_COOLDOWN_S", "30"))


def get_settings() -> Settings:
    return Settings()
