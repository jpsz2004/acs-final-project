from __future__ import annotations

import logging
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.services import JobService
from app.config import Settings, get_settings
from app.domain.commands import TextAnalysisCommand
from app.infrastructure.analyzer import SimpleTextAnalyzer
from app.infrastructure.repositories import InMemoryJobRepository
from app.infrastructure.worker import WorkerPool
from app.presentation.api import build_router


def create_app(*, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    logging.basicConfig(level=logging.INFO)

    repo = InMemoryJobRepository()
    command_queue: "queue.Queue[TextAnalysisCommand]" = queue.Queue(maxsize=settings.queue_maxsize)
    analyzer = SimpleTextAnalyzer()
    worker_pool = WorkerPool(
        worker_count=settings.worker_count,
        command_queue=command_queue,
        repo=repo,
        analyzer=analyzer,
        processing_delay_ms=settings.processing_delay_ms,
    )

    job_service = JobService(repo=repo, command_queue=command_queue)

    def job_service_provider() -> JobService:
        return job_service

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker_pool.start()
        yield
        worker_pool.stop()

    app = FastAPI(title="Historia 2 - Producer Consumer", lifespan=lifespan)
    app.include_router(build_router(job_service_provider=job_service_provider))

    return app
