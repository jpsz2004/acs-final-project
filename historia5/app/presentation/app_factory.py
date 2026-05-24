from __future__ import annotations

import asyncio
import logging
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.event_bus import EventBus
from app.application.handlers import JobCompletedHandler
from app.application.services import JobService, WebhookService
from app.config import Settings, get_settings
from app.domain.commands import TextAnalysisCommand
from app.domain.events import JobCompletedEvent
from app.infrastructure.analyzer import SimpleTextAnalyzer
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.notification_service import NotificationServiceImpl
from app.infrastructure.repositories import InMemoryJobRepository, InMemoryWebhookRepository
from app.infrastructure.webhook_client import HttpxWebhookClient
from app.infrastructure.worker import WorkerPool
from app.presentation.api import build_router
from app.presentation.websocket_manager import WebSocketManager


def create_app(*, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    logging.basicConfig(level=logging.INFO)

    repo = InMemoryJobRepository()
    webhook_repo = InMemoryWebhookRepository()
    command_queue: "queue.Queue[TextAnalysisCommand]" = queue.Queue(maxsize=settings.queue_maxsize)
    analyzer = SimpleTextAnalyzer()
    event_bus = EventBus()
    ws_manager = WebSocketManager()

    job_service = JobService(repo=repo, command_queue=command_queue)
    webhook_service = WebhookService(repo=webhook_repo)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()

        notification_service = NotificationServiceImpl(
            ws_manager=ws_manager,
            webhook_repo=webhook_repo,
            webhook_client=HttpxWebhookClient(),
            loop=loop,
            public_base_url=settings.public_base_url,
            max_retries=settings.webhook_max_retries,
            backoff_base_ms=settings.webhook_backoff_base_ms,
            circuit_breaker=CircuitBreaker(
                failure_threshold=settings.circuit_breaker_failure_threshold,
                cooldown_s=settings.circuit_breaker_cooldown_s,
            ),
        )

        event_bus.subscribe(JobCompletedEvent, JobCompletedHandler(notification_service=notification_service))

        worker_pool = WorkerPool(
            worker_count=settings.worker_count,
            command_queue=command_queue,
            repo=repo,
            analyzer=analyzer,
            event_bus=event_bus,
            processing_delay_ms=settings.processing_delay_ms,
            public_base_url=settings.public_base_url,
        )

        worker_pool.start()
        yield
        worker_pool.stop()

    app = FastAPI(title="Historia 5 - WebSocket Notifications", lifespan=lifespan)

    def job_service_provider() -> JobService:
        return job_service

    def webhook_service_provider() -> WebhookService:
        return webhook_service

    app.include_router(
        build_router(
            job_service_provider=job_service_provider,
            webhook_service_provider=webhook_service_provider,
            ws_manager=ws_manager,
            settings_provider=lambda: settings,
        )
    )

    return app


