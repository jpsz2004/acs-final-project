from __future__ import annotations

import queue

from app.application.errors import BatchTooLargeError
from app.application.ports import JobRepository, WebhookRepository
from app.domain.commands import TextAnalysisCommand
from app.domain.models import Job


class JobService:
    MAX_BATCH_SIZE = 100

    def __init__(self, *, repo: JobRepository, command_queue: "queue.Queue[TextAnalysisCommand]") -> None:
        self._repo = repo
        self._queue = command_queue

    def create_job(self, *, user_id: str, texts: list[str]) -> Job:
        if len(texts) > self.MAX_BATCH_SIZE:
            raise BatchTooLargeError(self.MAX_BATCH_SIZE)

        job = Job.new(user_id=user_id, texts=texts)
        self._repo.save(job)

        for text in job.texts:
            self._queue.put(TextAnalysisCommand(job_id=job.job_id, text_id=text.text_id))

        return job

    def get_job_for_user(self, *, job_id: str, user_id: str) -> Job:
        return self._repo.get_for_user(job_id, user_id)


class WebhookService:
    def __init__(self, *, repo: WebhookRepository) -> None:
        self._repo = repo

    def register_callback_url(self, *, user_id: str, callback_url: str) -> None:
        self._repo.set_callback_url(user_id=user_id, callback_url=callback_url)

    def get_callback_url(self, *, user_id: str) -> str | None:
        return self._repo.get_callback_url(user_id=user_id)
