from __future__ import annotations

import threading

from sqlalchemy import update
from sqlalchemy.orm import scoped_session

from app.application.errors import ForbiddenError, JobNotFoundError
from app.domain.models import Email, Job, JobStatus, Password, Text, TextStatus, User
from app.infrastructure.models import JobModel, TextModel, UserModel


# ─────────────────────────────────────────────────────────────────────────────
# In-memory repositories (used for tests and when DATABASE_URL is absent)
# ─────────────────────────────────────────────────────────────────────────────

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
        score: float | None,
        failed: bool,
        error: str | None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise JobNotFoundError(job_id)

            target = next((t for t in job.texts if t.text_id == text_id), None)
            if target is None:
                raise JobNotFoundError(f"text_id={text_id}")

            target.language = language
            target.sentiment = sentiment
            if score is not None:
                target.score = score
            target.error = error
            target.status = TextStatus.failed if failed else TextStatus.completed

            any_failed = any(t.status == TextStatus.failed for t in job.texts)
            all_done = all(
                t.status in (TextStatus.completed, TextStatus.failed) for t in job.texts
            )
            if all_done:
                job.status = JobStatus.failed if any_failed else JobStatus.completed
            else:
                job.status = JobStatus.processing

    def try_mark_notified(self, job_id: str) -> bool:
        """Atomic test-and-set: returns True only the first time for this job_id."""
        with self._lock:
            if job_id in self._notified_jobs:
                return False
            self._notified_jobs.add(job_id)
            return True


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._users_by_id: dict[str, User] = {}
        self._users_by_email: dict[str, User] = {}

    def save(self, user: User) -> None:
        with self._lock:
            self._users_by_id[user.user_id] = user
            self._users_by_email[user.email.value] = user

    def get_by_email(self, email: str) -> User | None:
        with self._lock:
            return self._users_by_email.get(email)

    def get_by_id(self, user_id: str) -> User | None:
        with self._lock:
            return self._users_by_id.get(user_id)


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


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL repositories (SQLAlchemy + scoped_session)
# ─────────────────────────────────────────────────────────────────────────────

class PostgresJobRepository:
    def __init__(self, *, session_factory: scoped_session) -> None:
        self._session_factory = session_factory

    def _session(self):
        return self._session_factory()

    def _remove(self) -> None:
        self._session_factory.remove()

    def save(self, job: Job) -> None:
        session = self._session()
        try:
            job_model = JobModel(
                id=job.job_id,
                user_id=job.user_id,
                status=job.status.value,
                notified=False,
            )
            session.add(job_model)
            session.flush()
            for text in job.texts:
                session.add(
                    TextModel(
                        id=text.text_id,
                        job_id=job.job_id,
                        content=text.content,
                        language=text.language,
                        sentiment=text.sentiment,
                        score=text.score,
                        status=text.status.value,
                        error=text.error,
                    )
                )
            session.commit()
        finally:
            self._remove()

    def get(self, job_id: str) -> Job:
        session = self._session()
        try:
            model = session.query(JobModel).filter_by(id=job_id).one_or_none()
            if model is None:
                raise JobNotFoundError(job_id)
            return self._hydrate(model)
        finally:
            self._remove()

    def get_for_user(self, job_id: str, user_id: str) -> Job:
        job = self.get(job_id)
        if job.user_id != user_id:
            raise ForbiddenError("Job does not belong to user")
        return job

    def set_text_processing(self, job_id: str, text_id: str) -> None:
        session = self._session()
        try:
            text_model = (
                session.query(TextModel)
                .join(JobModel)
                .filter(TextModel.id == text_id, JobModel.id == job_id)
                .one_or_none()
            )
            if text_model is None:
                raise JobNotFoundError(f"text_id={text_id}")
            if text_model.job.status == JobStatus.pending.value:
                text_model.job.status = JobStatus.processing.value
            text_model.status = TextStatus.processing.value
            session.commit()
        finally:
            self._remove()

    def set_text_result(
        self,
        job_id: str,
        text_id: str,
        *,
        language: str | None,
        sentiment: str | None,
        score: float | None,
        failed: bool,
        error: str | None,
    ) -> None:
        session = self._session()
        try:
            text_model = (
                session.query(TextModel)
                .join(JobModel)
                .filter(TextModel.id == text_id, JobModel.id == job_id)
                .one_or_none()
            )
            if text_model is None:
                raise JobNotFoundError(f"text_id={text_id}")

            text_model.language = language
            text_model.sentiment = sentiment
            if score is not None:
                text_model.score = score
            text_model.error = error
            text_model.status = TextStatus.failed.value if failed else TextStatus.completed.value

            job_model = text_model.job
            any_failed = any(t.status == TextStatus.failed.value for t in job_model.texts)
            all_done = all(
                t.status in (TextStatus.completed.value, TextStatus.failed.value)
                for t in job_model.texts
            )
            if all_done:
                job_model.status = JobStatus.failed.value if any_failed else JobStatus.completed.value
            else:
                job_model.status = JobStatus.processing.value

            session.commit()
        finally:
            self._remove()

    def try_mark_notified(self, job_id: str) -> bool:
        """
        Atomic exactly-once guard using a conditional UPDATE.

        Issues: UPDATE jobs SET notified=true WHERE id=? AND notified=false
        Returns True only if the row was actually updated (i.e. this is the
        first worker to call this for the job). All subsequent callers get
        False because notified is already true.

        This is the correct way to implement this in a multi-process or
        distributed environment: never rely on a SELECT + UPDATE pair,
        which would have a race window between the two statements.
        """
        session = self._session()
        try:
            result = session.execute(
                update(JobModel)
                .where(JobModel.id == job_id, JobModel.notified == False)  # noqa: E712
                .values(notified=True)
                .execution_options(synchronize_session="fetch")
            )
            session.commit()
            return result.rowcount == 1
        finally:
            self._remove()

    def _hydrate(self, model: JobModel) -> Job:
        texts = [
            Text(
                text_id=t.id,
                content=t.content,
                language=t.language,
                sentiment=t.sentiment,
                score=t.score,
                status=TextStatus(t.status),
                error=t.error,
            )
            for t in model.texts
        ]
        return Job(
            job_id=model.id,
            user_id=model.user_id,
            status=JobStatus(model.status),
            texts=texts,
        )


class PostgresUserRepository:
    def __init__(self, *, session_factory: scoped_session) -> None:
        self._session_factory = session_factory

    def _session(self):
        return self._session_factory()

    def _remove(self) -> None:
        self._session_factory.remove()

    def save(self, user: User) -> None:
        session = self._session()
        try:
            session.add(
                UserModel(
                    id=user.user_id,
                    email=user.email.value,
                    password_hash=user.password.hashed,
                )
            )
            session.commit()
        finally:
            self._remove()

    def get_by_email(self, email: str) -> User | None:
        session = self._session()
        try:
            model = session.query(UserModel).filter_by(email=email).one_or_none()
            if model is None:
                return None
            return User(
                user_id=model.id,
                email=Email(model.email),
                password=Password(hashed=model.password_hash),
            )
        finally:
            self._remove()

    def get_by_id(self, user_id: str) -> User | None:
        session = self._session()
        try:
            model = session.query(UserModel).filter_by(id=user_id).one_or_none()
            if model is None:
                return None
            return User(
                user_id=model.id,
                email=Email(model.email),
                password=Password(hashed=model.password_hash),
            )
        finally:
            self._remove()