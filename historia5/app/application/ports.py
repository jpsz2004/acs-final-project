from __future__ import annotations

from typing import Protocol

from app.domain.events import JobCompletedEvent
from app.domain.models import Job


class JobRepository(Protocol):
    def save(self, job: Job) -> None: ...

    def get(self, job_id: str) -> Job: ...

    def get_for_user(self, job_id: str, user_id: str) -> Job: ...

    def set_text_processing(self, job_id: str, text_id: str) -> None: ...

    def set_text_result(
        self,
        job_id: str,
        text_id: str,
        *,
        language: str | None,
        sentiment: str | None,
        failed: bool,
        error: str | None,
    ) -> None: ...

    def try_mark_notified(self, job_id: str) -> bool: ...


class WebhookRepository(Protocol):
    def set_callback_url(self, *, user_id: str, callback_url: str) -> None: ...

    def get_callback_url(self, *, user_id: str) -> str | None: ...


class TextAnalyzer(Protocol):
    def analyze(self, text: str) -> tuple[str | None, str]: ...


class NotificationService(Protocol):
    def notify_job_completed(self, event: JobCompletedEvent) -> None: ...
