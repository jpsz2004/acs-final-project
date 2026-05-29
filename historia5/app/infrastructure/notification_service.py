from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor

from app.application.ports import NotificationService, WebhookRepository
from app.domain.events import JobCompletedEvent
from app.infrastructure.circuit_breaker import CircuitBreaker
from app.infrastructure.webhook_client import WebhookClient

# Imported lazily only for typing; avoids circular imports at runtime.
from app.presentation.websocket_manager import WebSocketManager  # noqa: E402  isort: skip

logger = logging.getLogger(__name__)


class NotificationServiceImpl(NotificationService):
    def __init__(
        self,
        *,
        ws_manager: "WebSocketManager",
        webhook_repo: WebhookRepository,
        webhook_client: WebhookClient,
        loop: asyncio.AbstractEventLoop,
        public_base_url: str | None,
        max_retries: int,
        backoff_base_ms: int,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        self._ws_manager = ws_manager
        self._webhook_repo = webhook_repo
        self._webhook_client = webhook_client
        self._loop = loop
        self._public_base_url = public_base_url
        self._max_retries = max(0, max_retries)
        self._backoff_base_ms = max(0, backoff_base_ms)
        self._cb = circuit_breaker
        self._executor = ThreadPoolExecutor(max_workers=4)

    def notify_job_completed(self, event: JobCompletedEvent) -> None:
        payload = {
            "type": "job_completed",
            "job_id": event.job_id,
            "results_url": event.results_url,
        }

        # WebSocket: schedule in the main event loop, non-blocking for workers.
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._ws_manager.send_to_user(event.user_id, payload),
                self._loop,
            )
            fut.add_done_callback(lambda f: f.exception() and logger.debug("WS send error: %s", f.exception()))
        except Exception:  # noqa: BLE001
            logger.exception("Failed to schedule WS notification")

        # Webhook: fire-and-forget via thread pool.
        callback_url = self._webhook_repo.get_callback_url(user_id=event.user_id)
        if callback_url:
            self._executor.submit(self._send_webhook_with_retry, callback_url, payload)

    def _send_webhook_with_retry(self, url: str, payload: dict) -> None:
        if not self._cb.allow(url):
            logger.info("Circuit breaker open for %s", url)
            return

        for attempt in range(self._max_retries + 1):
            try:
                self._webhook_client.post_json(url=url, payload=payload)
                self._cb.record_success(url)
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Webhook attempt %s failed url=%s error=%s", attempt + 1, url, exc)
                self._cb.record_failure(url)

                if attempt >= self._max_retries:
                    return

                backoff_s = (self._backoff_base_ms / 1000.0) * (2**attempt)
                time.sleep(backoff_s)



