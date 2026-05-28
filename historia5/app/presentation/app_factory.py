from __future__ import annotations

import asyncio
import logging
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.application.event_bus import EventBus
from app.application.handlers import JobCompletedHandler
from app.application.services import AuthService, JobService, JwtService, WebhookService
from app.config import Settings, get_settings
from app.domain.commands import TextAnalysisCommand
from app.domain.events import JobCompletedEvent
from app.infrastructure.analyzer import SimpleTextAnalyzer
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.database import create_engine_from_url, create_session_factory, init_db
from app.infrastructure.hasher import BcryptHasher
from app.infrastructure.notification_service import NotificationServiceImpl
from app.infrastructure.repositories import (
    InMemoryJobRepository,
    InMemoryUserRepository,
    InMemoryWebhookRepository,
    PostgresJobRepository,
    PostgresUserRepository,
)
from app.infrastructure.webhook_client import HttpxWebhookClient
from app.infrastructure.worker import WorkerPool
from app.presentation.api import build_router
from app.presentation.websocket_manager import WebSocketManager


def create_app(*, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    logging.basicConfig(level=logging.INFO)

    # Database and repositories
    if settings.database_url:
        engine = create_engine_from_url(settings.database_url)
        init_db(engine)
        session_factory = create_session_factory(engine)
        repo = PostgresJobRepository(session_factory=session_factory)
        user_repo = PostgresUserRepository(session_factory=session_factory)
    else:
        repo = InMemoryJobRepository()
        user_repo = InMemoryUserRepository()

    webhook_repo = InMemoryWebhookRepository()
    command_queue: "queue.Queue[TextAnalysisCommand]" = queue.Queue(maxsize=settings.queue_maxsize)
    analyzer = SimpleTextAnalyzer()
    event_bus = EventBus()
    ws_manager = WebSocketManager()

    job_service = JobService(repo=repo, command_queue=command_queue)
    webhook_service = WebhookService(repo=webhook_repo)
    jwt_service = JwtService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiration_seconds=settings.jwt_expiration_seconds,
    )
    auth_service = AuthService(user_repo=user_repo, hasher=BcryptHasher(), jwt_service=jwt_service)

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

    def auth_service_provider() -> AuthService:
        return auth_service

    def jwt_service_provider() -> JwtService:
        return jwt_service

    app.include_router(
        build_router(
            job_service_provider=job_service_provider,
            webhook_service_provider=webhook_service_provider,
            auth_service_provider=auth_service_provider,
            ws_manager=ws_manager,
            jwt_service_provider=jwt_service_provider,
        )
    )

    return app

