from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    worker_count: int = int(os.getenv("WORKERS_COUNT", "4"))
    processing_delay_ms: int = int(os.getenv("PROCESSING_DELAY_MS", "50"))
    api_key: str | None = os.getenv("API_KEY")
    queue_maxsize: int = int(os.getenv("QUEUE_MAXSIZE", "0"))


def get_settings() -> Settings:
    return Settings()
