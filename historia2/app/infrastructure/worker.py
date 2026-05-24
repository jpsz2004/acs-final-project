from __future__ import annotations

import logging
import queue
import threading
import time

from app.application.ports import JobRepository, TextAnalyzer
from app.domain.commands import TextAnalysisCommand

logger = logging.getLogger(__name__)


class Worker(threading.Thread):
    def __init__(
        self,
        *,
        name: str,
        command_queue: "queue.Queue[TextAnalysisCommand]",
        repo: JobRepository,
        analyzer: TextAnalyzer,
        stop_event: threading.Event,
        processing_delay_ms: int,
    ) -> None:
        super().__init__(name=name, daemon=True)
        self._queue = command_queue
        self._repo = repo
        self._analyzer = analyzer
        self._stop_event = stop_event
        self._delay_s = max(0, processing_delay_ms) / 1000.0

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                command = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                self._repo.set_text_processing(command.job_id, command.text_id)

                if self._delay_s:
                    time.sleep(self._delay_s)

                job = self._repo.get(command.job_id)
                text = next(t for t in job.texts if t.text_id == command.text_id)
                language, sentiment = self._analyzer.analyze(text.content)

                self._repo.set_text_result(
                    command.job_id,
                    command.text_id,
                    language=language,
                    sentiment=sentiment,
                    failed=False,
                    error=None,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Worker failed processing command job_id=%s text_id=%s", command.job_id, command.text_id)
                try:
                    self._repo.set_text_result(
                        command.job_id,
                        command.text_id,
                        language=None,
                        sentiment=None,
                        failed=True,
                        error=str(exc),
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to persist error result")
            finally:
                self._queue.task_done()


class WorkerPool:
    def __init__(
        self,
        *,
        worker_count: int,
        command_queue: "queue.Queue[TextAnalysisCommand]",
        repo: JobRepository,
        analyzer: TextAnalyzer,
        processing_delay_ms: int,
    ) -> None:
        self._stop_event = threading.Event()
        self._workers: list[Worker] = [
            Worker(
                name=f"worker-{i+1}",
                command_queue=command_queue,
                repo=repo,
                analyzer=analyzer,
                stop_event=self._stop_event,
                processing_delay_ms=processing_delay_ms,
            )
            for i in range(max(1, worker_count))
        ]

    def start(self) -> None:
        for w in self._workers:
            w.start()

    def stop(self) -> None:
        self._stop_event.set()
        for w in self._workers:
            w.join(timeout=2)
