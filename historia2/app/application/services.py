from __future__ import annotations

import datetime
import queue

import jwt

from app.application.errors import (
    ApplicationError,
    AuthenticationError,
    BatchTooLargeError,
    ForbiddenError,
    JobNotFoundError,
    UserAlreadyExistsError,
)
from app.application.ports import JobRepository, TextAnalyzer, UserRepository
from app.domain.commands import TextAnalysisCommand
from app.domain.models import Email, Job, JobStatus, Text, TextStatus, User, Password


class JobService:
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        *,
        repo: JobRepository,
        command_queue: "queue.Queue[TextAnalysisCommand]",
    ) -> None:
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

    def get_job_results(self, *, job_id: str, user_id: str, limit: int = 20, offset: int = 0) -> tuple[Job, list[Text]]:
        job = self.get_job_for_user(job_id=job_id, user_id=user_id)
        return job, job.texts[offset : offset + limit]


class ReportService:
    def __init__(self, *, repo: JobRepository) -> None:
        self._repo = repo

    def get_report(self, *, job_id: str, user_id: str) -> dict[str, object]:
        job = self._repo.get_for_user(job_id, user_id)
        completed = sum(1 for text in job.texts if text.status == TextStatus.completed)
        failed = sum(1 for text in job.texts if text.status == TextStatus.failed)
        processed = completed + failed
        average_score = 0.0
        if processed:
            average_score = sum(text.score for text in job.texts if text.status in (TextStatus.completed, TextStatus.failed)) / processed

        return {
            "job_id": job.job_id,
            "total_texts": len(job.texts),
            "processed_texts": processed,
            "completed_texts": completed,
            "failed_texts": failed,
            "average_score": average_score,
        }


class JwtService:
    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        expiration_seconds: int = 3600,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expiration_seconds = expiration_seconds

    def create_token(self, user_id: str) -> str:
        payload = {
            "sub": user_id,
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=self._expiration_seconds),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def verify_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            subject = payload.get("sub")
            if not isinstance(subject, str):
                raise AuthenticationError("Invalid token payload")
            return subject
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Invalid or expired token") from exc


class AuthService:
    def __init__(
        self,
        *,
        user_repo: UserRepository,
        hasher: object,
        jwt_service: JwtService,
    ) -> None:
        self._user_repo = user_repo
        self._hasher = hasher
        self._jwt_service = jwt_service

    def register(self, *, email: str, password: str) -> str:
        user_email = Email(email)
        existing_user = self._user_repo.get_by_email(user_email.value)
        if existing_user is not None:
            raise UserAlreadyExistsError("User already exists")

        hashed_password = self._hasher.hash_password(password)
        user = User.new(email=user_email, password=Password(hashed=hashed_password))
        self._user_repo.save(user)
        return self._jwt_service.create_token(user.user_id)

    def login(self, *, email: str, password: str) -> str:
        user = self._user_repo.get_by_email(email)
        if user is None or not self._hasher.verify(password, user.password.hashed):
            raise AuthenticationError("Invalid email or password")
        return self._jwt_service.create_token(user.user_id)
