"""
Application services for Historia 8.

Each service orchestrates one simulation scenario and returns a
structured result object so the presentation layer (main.py) can
display statistics without knowing implementation details.

Services
--------
- ProducerConsumerService  : Part 1 — LMS grading simulation.
- ReadersWritersService    : Part 2 — concurrent grade access.
- BarrierService           : Part 3 — synchronised exam start.
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from dataclasses import dataclass, field

from app.domain.models import Assignment, GradeRecord
from app.infrastructure.repositories import GradeRepository, PaymentConfigRepository
from app.infrastructure.workers import AssignmentWorker

logger = logging.getLogger(__name__)


# ======================================================================
# Part 1 — Producer-Consumer
# ======================================================================

@dataclass
class ProducerConsumerResult:
    total_assignments: int
    graded_assignments: int
    elapsed_seconds: float
    throughput: float          # assignments / second
    grades: list[GradeRecord]
    worker_counts: dict[str, int]  # worker_id → graded count


class ProducerConsumerService:
    """
    Orchestrates the LMS grading simulation.

    - 15 student producers each submit 1 assignment.
    - 3 AssignmentWorker threads grade them concurrently.
    - Queue capacity is capped at 10 (bounded buffer).
    - Producers block on put() when the queue is full — they do NOT
      drop submissions; they wait until a worker frees a slot.
    """

    QUEUE_CAPACITY = 10
    NUM_WORKERS = 3
    NUM_STUDENTS = 15
    COURSES = ["CS101", "MATH201", "PHYS301"]

    def run(self) -> ProducerConsumerResult:
        repo = GradeRepository()
        task_queue: queue.Queue[Assignment] = queue.Queue(maxsize=self.QUEUE_CAPACITY)
        stop_event = threading.Event()

        # --- Start workers (consumers) ---
        workers = [
            AssignmentWorker(
                worker_id=str(i + 1),
                task_queue=task_queue,
                repo=repo,
                stop_event=stop_event,
            )
            for i in range(self.NUM_WORKERS)
        ]
        for w in workers:
            w.start()

        # --- Launch producer threads ---
        start = time.perf_counter()
        producer_threads: list[threading.Thread] = []

        def produce(student_id: str) -> None:
            course = random.choice(self.COURSES)
            assignment = Assignment.new(
                student_id=student_id,
                course_id=course,
                answer_text=f"Answer from {student_id} for {course}",
            )
            logger.info(
                "[Producer] student=%s enqueuing assignment %s (course=%s)",
                student_id,
                assignment.assignment_id,
                course,
            )
            # Blocking put — waits if queue is full (bounded buffer).
            task_queue.put(assignment)
            logger.info("[Producer] student=%s enqueued", student_id)

        for i in range(self.NUM_STUDENTS):
            t = threading.Thread(
                target=produce,
                args=(f"student-{i + 1:02d}",),
                name=f"producer-{i + 1}",
                daemon=True,
            )
            producer_threads.append(t)

        for t in producer_threads:
            t.start()
        for t in producer_threads:
            t.join()

        # --- Wait until all tasks are processed ---
        task_queue.join()
        stop_event.set()
        for w in workers:
            w.join(timeout=3)

        elapsed = time.perf_counter() - start
        grades = repo.all_grades()

        return ProducerConsumerResult(
            total_assignments=self.NUM_STUDENTS,
            graded_assignments=len(grades),
            elapsed_seconds=round(elapsed, 3),
            throughput=round(len(grades) / elapsed, 3) if elapsed > 0 else 0.0,
            grades=grades,
            worker_counts={w.name: w.graded_count for w in workers},
        )


# ======================================================================
# Part 2 — Readers-Writers
# ======================================================================

@dataclass
class ReaderWriterStats:
    writer_id: str
    writes_completed: int
    was_starved: bool  # True if wait time exceeded threshold


@dataclass
class ReadersWritersResult:
    elapsed_seconds: float
    total_reads: int
    total_writes: int
    writer_stats: list[ReaderWriterStats]
    starvation_detected: bool


class ReadersWritersService:
    """
    Simulates concurrent grade access with a ReadWriteLock.

    Scenario (from the taller spec):
    - 10 reader threads (students) each read a grade 5 times.
    - 2 writer threads (professors) each update a grade 3 times,
      with a 0.5 s sleep between writes.
    - Writers have priority: new readers wait while any writer queues.
    - Logs show when each reader starts/finishes and when writers write.

    Starvation detection
    --------------------
    A writer is considered "starved" if it had to wait more than
    2 seconds to acquire the write lock (indicates reader flooding).
    With writer-priority semantics this should not occur, but the
    check validates the implementation.
    """

    NUM_READERS = 10
    NUM_WRITERS = 2
    READS_PER_READER = 5
    WRITES_PER_WRITER = 3
    WRITE_INTERVAL_S = 0.5
    STARVATION_THRESHOLD_S = 2.0

    def run(self) -> ReadersWritersResult:
        repo = GradeRepository()
        # Pre-populate with some grades so readers have data.
        for i in range(self.NUM_READERS):
            repo.write_grade(
                GradeRecord(
                    student_id=f"student-{i + 1:02d}",
                    course_id="CS101",
                    assignment_id=f"init-{i}",
                    score=float(50 + i),
                )
            )

        total_reads: list[int] = [0]
        total_writes: list[int] = [0]
        reads_lock = threading.Lock()
        writes_lock = threading.Lock()

        writer_stats: list[ReaderWriterStats] = []
        stats_lock = threading.Lock()

        start = time.perf_counter()

        # --- Reader threads ---
        # Note: we call repo.read_grade() directly. That method already
        # acquires/releases the read lock internally. We only add the
        # log messages around the call to show lock events clearly.
        def reader_task(reader_id: str) -> None:
            for _ in range(self.READS_PER_READER):
                student = f"student-{random.randint(1, self.NUM_READERS):02d}"
                logger.info("[Reader %s] acquiring read lock (target=%s)", reader_id, student)
                # repo.read_grade() handles acquire_read / release_read internally.
                result = repo.read_grade(student_id=student, course_id="CS101")
                logger.info(
                    "[Reader %s] finished reading %s — score=%s",
                    reader_id, student,
                    f"{result.score:.2f}" if result else "N/A",
                )
                with reads_lock:
                    total_reads[0] += 1
                time.sleep(random.uniform(0.0, 0.05))

        # --- Writer threads ---
        # We measure the wait time by timing the write_grade() call,
        # which includes the acquire_write() + critical section + release.
        def writer_task(writer_id: str) -> None:
            wait_times: list[float] = []
            for i in range(self.WRITES_PER_WRITER):
                student = f"student-{random.randint(1, self.NUM_READERS):02d}"
                new_score = round(random.uniform(0.0, 100.0), 2)

                logger.info("[Writer %s] waiting for write lock (target=%s)", writer_id, student)
                wait_start = time.perf_counter()
                # write_grade() handles acquire_write / release_write internally.
                repo.write_grade(
                    GradeRecord(
                        student_id=student,
                        course_id="CS101",
                        assignment_id=f"update-{writer_id}-{i}",
                        score=new_score,
                    )
                )
                wait_time = time.perf_counter() - wait_start
                wait_times.append(wait_time)
                logger.info(
                    "[Writer %s] WROTE grade for %s — score=%.2f (elapsed %.3fs)",
                    writer_id, student, new_score, wait_time,
                )

                with writes_lock:
                    total_writes[0] += 1

                if i < self.WRITES_PER_WRITER - 1:
                    time.sleep(self.WRITE_INTERVAL_S)

            max_wait = max(wait_times) if wait_times else 0.0
            starved = max_wait > self.STARVATION_THRESHOLD_S
            with stats_lock:
                writer_stats.append(
                    ReaderWriterStats(
                        writer_id=writer_id,
                        writes_completed=self.WRITES_PER_WRITER,
                        was_starved=starved,
                    )
                )

        threads: list[threading.Thread] = []
        for i in range(self.NUM_READERS):
            threads.append(
                threading.Thread(target=reader_task, args=(f"R{i + 1:02d}",), daemon=True)
            )
        for i in range(self.NUM_WRITERS):
            threads.append(
                threading.Thread(target=writer_task, args=(f"W{i + 1}",), daemon=True)
            )

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.perf_counter() - start
        starvation = any(s.was_starved for s in writer_stats)

        return ReadersWritersResult(
            elapsed_seconds=round(elapsed, 3),
            total_reads=total_reads[0],
            total_writes=total_writes[0],
            writer_stats=writer_stats,
            starvation_detected=starvation,
        )


# ======================================================================
# Part 3 — Barrier
# ======================================================================

@dataclass
class StudentBarrierRecord:
    student_id: str
    arrival_time: float   # seconds after simulation start
    start_time: float     # seconds after all students arrived


@dataclass
class BarrierResult:
    elapsed_seconds: float
    student_records: list[StudentBarrierRecord]
    max_wait_seconds: float   # longest wait at the barrier
    all_started_simultaneously: bool  # True if spread < 50 ms


class BarrierService:
    """
    Simulates a synchronised exam start using threading.Barrier.

    - N=5 student threads each arrive at different times
      (random sleep 0.1 – 1.5 s before calling barrier.wait()).
    - Once all 5 are waiting, the barrier releases all simultaneously.
    - Each student logs "ready" before the barrier and "started" after.

    The result validates that all exam-start timestamps are within
    50 ms of each other (simultaneous release guarantee).
    """

    NUM_STUDENTS = 5
    MAX_ARRIVAL_DELAY_S = 1.5

    def run(self) -> BarrierResult:
        records: list[StudentBarrierRecord] = []
        records_lock = threading.Lock()
        sim_start = time.perf_counter()

        barrier = threading.Barrier(self.NUM_STUDENTS)

        def student_task(student_id: str) -> None:
            delay = random.uniform(0.1, self.MAX_ARRIVAL_DELAY_S)
            time.sleep(delay)

            arrival = time.perf_counter() - sim_start
            logger.info(
                "[Student %s] is ready (arrived at %.3fs) — waiting at barrier",
                student_id, arrival,
            )

            barrier.wait()  # ← All students block here until all N arrive.

            exam_start = time.perf_counter() - sim_start
            logger.info(
                "[Student %s] starts the exam at t=%.3fs",
                student_id, exam_start,
            )

            with records_lock:
                records.append(
                    StudentBarrierRecord(
                        student_id=student_id,
                        arrival_time=round(arrival, 4),
                        start_time=round(exam_start, 4),
                    )
                )

        threads = [
            threading.Thread(
                target=student_task,
                args=(f"S{i + 1}",),
                name=f"student-{i + 1}",
                daemon=True,
            )
            for i in range(self.NUM_STUDENTS)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.perf_counter() - sim_start
        start_times = [r.start_time for r in records]
        arrival_times = [r.arrival_time for r in records]
        spread = max(start_times) - min(start_times) if start_times else 0.0
        max_wait = max(
            r.start_time - r.arrival_time for r in records
        ) if records else 0.0

        return BarrierResult(
            elapsed_seconds=round(elapsed, 3),
            student_records=sorted(records, key=lambda r: r.arrival_time),
            max_wait_seconds=round(max_wait, 4),
            all_started_simultaneously=spread < 0.05,
        )
