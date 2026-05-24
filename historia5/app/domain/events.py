from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobCompletedEvent:
    job_id: str
    user_id: str
    results_url: str
