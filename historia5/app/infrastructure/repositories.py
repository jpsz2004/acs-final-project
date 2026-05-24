from __future__ import annotations

import threading

from app.application.errors import ForbiddenError, JobNotFoundError
from app.domain.models import Job, JobStatus, TextStatus


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._notified_jobs: set[str] = set()

    def save(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def get(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)
            return job

    def get_for_user(self, job_id: str, user_id: str) -> Job:
        job = self.get(job_id)
        if job.user_id != user_id:
            raise ForbiddenError("Job does not belong to user")
        return job

    def set_text_processing(self, job_id: str, text_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)

            if job.status == JobStatus.pending:
                job.status = JobStatus.processing

            for text in job.texts:
                if text.text_id == text_id:
                    text.status = TextStatus.processing
                    return

            raise JobNotFoundError(f"text_id={text_id}")

    def set_text_result(
        self,
        job_id: str,
        text_id: str,
        *,
        language: str | None,
        sentiment: str | None,
        failed: bool,
        error: str | None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)

            target = None
            for text in job.texts:
                if text.text_id == text_id:
                    target = text
                    break

            if target is None:
                raise JobNotFoundError(f"text_id={text_id}")

            target.language = language
            target.sentiment = sentiment
            target.error = error
            target.status = TextStatus.failed if failed else TextStatus.completed

            any_failed = any(t.status == TextStatus.failed for t in job.texts)
            all_done = all(t.status in (TextStatus.completed, TextStatus.failed) for t in job.texts)

            if all_done:
                job.status = JobStatus.failed if any_failed else JobStatus.completed
            else:
                job.status = JobStatus.processing

    def try_mark_notified(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._notified_jobs:
                return False
            self._notified_jobs.add(job_id)
            return True


class InMemoryWebhookRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._callbacks: dict[str, str] = {}

    def set_callback_url(self, *, user_id: str, callback_url: str) -> None:
        with self._lock:
            self._callbacks[user_id] = callback_url

    def get_callback_url(self, *, user_id: str) -> str | None:
        with self._lock:
            return self._callbacks.get(user_id)
