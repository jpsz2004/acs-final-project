"""
Workers for the LMS Producer-Consumer simulation (Part 1).

AssignmentWorker
----------------
A daemon thread that continuously pulls Assignment objects from a
shared queue, simulates grading with a random sleep, generates a
random score (0–100), stores the result via GradeRepository, and
marks the queue task as done.

The worker respects a threading.Event for clean shutdown: when the
event is set AND the queue is empty, the thread exits gracefully.

Design choices
--------------
- daemon=True  : the process exits even if workers are still running,
                 acting as a safety net. Proper shutdown uses the event.
- task_done()  : always called in a finally block so Queue.join()
                 never deadlocks even when an exception occurs.
- Random sleep : simulates variable grading time (0.5 – 2.0 s).
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time

from app.domain.models import Assignment, AssignmentStatus, GradeRecord
from app.infrastructure.repositories import GradeRepository

logger = logging.getLogger(__name__)


class AssignmentWorker(threading.Thread):
    """
    Consumer thread: grades assignments taken from a shared queue.

    Parameters
    ----------
    worker_id : str
        Human-readable identifier used in log messages.
    task_queue : queue.Queue[Assignment]
        Shared bounded queue populated by producer threads.
    repo : GradeRepository
        Shared repository where grades are stored (thread-safe).
    stop_event : threading.Event
        Set by the orchestrator to signal a graceful shutdown.
    """

    def __init__(
        self,
        *,
        worker_id: str,
        task_queue: "queue.Queue[Assignment]",
        repo: GradeRepository,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name=f"worker-{worker_id}", daemon=True)
        self._worker_id = worker_id
        self._queue = task_queue
        self._repo = repo
        self._stop_event = stop_event
        self.graded_count: int = 0

    def run(self) -> None:
        logger.info("[Worker %s] started", self._worker_id)

        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                # Non-blocking get so the stop_event can be checked.
                assignment: Assignment = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                self._grade(assignment)
            except Exception:
                logger.exception(
                    "[Worker %s] unexpected error grading assignment %s",
                    self._worker_id,
                    assignment.assignment_id,
                )
            finally:
                self._queue.task_done()

        logger.info("[Worker %s] stopped — graded %d assignments", self._worker_id, self.graded_count)

    def _grade(self, assignment: Assignment) -> None:
        """Simulate grading: random sleep + random score."""
        assignment.status = AssignmentStatus.grading
        delay = random.uniform(0.5, 2.0)
        logger.info(
            "[Worker %s] grading assignment %s (student=%s, course=%s) — %.2fs",
            self._worker_id,
            assignment.assignment_id,
            assignment.student_id,
            assignment.course_id,
            delay,
        )
        time.sleep(delay)

        score = round(random.uniform(0.0, 100.0), 2)
        assignment.grade = score
        assignment.status = AssignmentStatus.graded

        record = GradeRecord(
            student_id=assignment.student_id,
            course_id=assignment.course_id,
            assignment_id=assignment.assignment_id,
            score=score,
        )
        self._repo.write_grade(record)
        self.graded_count += 1

        logger.info(
            "[Worker %s] graded assignment %s — score=%.2f",
            self._worker_id,
            assignment.assignment_id,
            score,
        )
