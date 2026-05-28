from __future__ import annotations

import logging
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.services import AuthService, JobService, JwtService, ReportService
from app.config import Settings, get_settings
from app.domain.commands import TextAnalysisCommand
from app.infrastructure.analyzer import SimpleTextAnalyzer
from app.infrastructure.database import create_engine_from_url, create_session_factory, init_db
from app.infrastructure.hasher import BcryptHasher
from app.infrastructure.repositories import (
    InMemoryJobRepository,
    InMemoryUserRepository,
    PostgresJobRepository,
    PostgresUserRepository,
)
from app.infrastructure.worker import WorkerPool
from app.presentation.api import build_router


def create_app(*, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    logging.basicConfig(level=logging.INFO)

    if settings.database_url:
        engine = create_engine_from_url(settings.database_url)
        init_db(engine)
        session_factory = create_session_factory(engine)
        job_repo = PostgresJobRepository(session_factory=session_factory)
        user_repo = PostgresUserRepository(session_factory=session_factory)
    else:
        job_repo = InMemoryJobRepository()
        user_repo = InMemoryUserRepository()

    command_queue: "queue.Queue[TextAnalysisCommand]" = queue.Queue(maxsize=settings.queue_maxsize)
    analyzer = SimpleTextAnalyzer()
    worker_pool = WorkerPool(
        worker_count=settings.worker_count,
        command_queue=command_queue,
        repo=job_repo,
        analyzer=analyzer,
        processing_delay_ms=settings.processing_delay_ms,
    )

    jwt_service = JwtService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiration_seconds=settings.jwt_expiration_seconds,
    )
    auth_service = AuthService(user_repo=user_repo, hasher=BcryptHasher(), jwt_service=jwt_service)
    job_service = JobService(repo=job_repo, command_queue=command_queue)
    report_service = ReportService(repo=job_repo)

    def job_service_provider() -> JobService:
        return job_service

    def auth_service_provider() -> AuthService:
        return auth_service

    def report_service_provider() -> ReportService:
        return report_service

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker_pool.start()
        yield
        worker_pool.stop()

    app = FastAPI(title="Historia 2 - Producer Consumer", lifespan=lifespan)
    app.include_router(
        build_router(
            job_service_provider=job_service_provider,
            auth_service_provider=auth_service_provider,
            report_service_provider=report_service_provider,
        )
    )

    return app
