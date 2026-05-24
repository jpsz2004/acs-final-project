from __future__ import annotations

from app.application.ports import NotificationService
from app.domain.events import JobCompletedEvent


class JobCompletedHandler:
    def __init__(self, *, notification_service: NotificationService) -> None:
        self._notification_service = notification_service

    def __call__(self, event: JobCompletedEvent) -> None:
        self._notification_service.notify_job_completed(event)
