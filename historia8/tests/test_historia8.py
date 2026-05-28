"""
Tests for Historia 8 — LMS Platform.

Test strategy
=============
Each part is tested at two levels:

1. Unit level  — primitive behaviour in isolation
   (ReadWriteLock invariants, GradeRepository thread-safety,
    AssignmentWorker produces correct records, Barrier releases
    all threads simultaneously).

2. Integration level — full simulation via application services
   (ProducerConsumerService, ReadersWritersService, BarrierService).

Concurrency tests use threading.Event and counters protected by
threading.Lock to observe interleaving without relying on timing.

Run with:
    pytest tests/ -v
    pytest tests/ -v --tb=short -q    ← quieter output
"""

from __future__ import annotations

import queue
import random
import threading
import time

import pytest

from app.application.services import (
    BarrierService,
    ProducerConsumerService,
    ReadersWritersService,
)
from app.domain.models import Assignment, GradeRecord
from app.infrastructure.locks import ReadWriteLock
from app.infrastructure.repositories import GradeRepository, PaymentConfigRepository
from app.infrastructure.workers import AssignmentWorker


# ======================================================================
# Part 1 — ReadWriteLock unit tests
# ======================================================================

class TestReadWriteLock:
    """Unit tests for ReadWriteLock invariants."""

    def test_single_reader_acquires_and_releases(self) -> None:
        lock = ReadWriteLock()
        lock.acquire_read()
        assert lock._readers_active == 1
        lock.release_read()
        assert lock._readers_active == 0

    def test_multiple_concurrent_readers_allowed(self) -> None:
        """Several readers must be able to hold the lock at the same time."""
        lock = ReadWriteLock()
        N = 8
        acquired = [0]
        inside_lock = threading.Lock()

        barrier_in = threading.Barrier(N)
        barrier_out = threading.Barrier(N)

        def reader() -> None:
            lock.acquire_read()
            try:
                barrier_in.wait()          # All N readers inside simultaneously.
                with inside_lock:
                    acquired[0] += 1
                barrier_out.wait()
            finally:
                lock.release_read()

        threads = [threading.Thread(target=reader, daemon=True) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3)

        assert acquired[0] == N, "Not all readers entered concurrently"

    def test_writer_gets_exclusive_access(self) -> None:
        """While a writer holds the lock, no reader or other writer may enter."""
        lock = ReadWriteLock()
        log: list[str] = []
        log_lock = threading.Lock()

        write_started = threading.Event()
        write_release = threading.Event()

        def writer() -> None:
            lock.acquire_write()
            with log_lock:
                log.append("write-start")
            write_started.set()
            write_release.wait()
            with log_lock:
                log.append("write-end")
            lock.release_write()

        def reader() -> None:
            write_started.wait()  # Ensure writer is inside first.
            lock.acquire_read()
            with log_lock:
                log.append("read")
            lock.release_read()

        wt = threading.Thread(target=writer, daemon=True)
        rt = threading.Thread(target=reader, daemon=True)
        wt.start()
        wt_started = write_started.wait(timeout=2)
        assert wt_started
        rt.start()
        time.sleep(0.05)  # Give reader a chance to (incorrectly) acquire.

        # Reader must not have entered yet — writer still holds the lock.
        assert "read" not in log, "Reader entered while writer was active"

        write_release.set()
        rt.join(timeout=2)
        wt.join(timeout=2)

        assert log == ["write-start", "write-end", "read"]

    def test_writer_priority_blocks_new_readers(self) -> None:
        """
        When a writer is waiting, new readers must block.

        Sequence:
        1. Reader-1 acquires the read lock.
        2. Writer-1 queues for write (increments _writers_waiting).
        3. Reader-2 tries to acquire read — must block.
        4. Reader-1 releases → Writer-1 runs → releases.
        5. Reader-2 finally acquires.
        """
        lock = ReadWriteLock()
        log: list[str] = []
        log_lock = threading.Lock()

        r1_acquired = threading.Event()
        w1_queued = threading.Event()
        r1_release = threading.Event()

        def reader1() -> None:
            lock.acquire_read()
            with log_lock:
                log.append("r1-start")
            r1_acquired.set()
            r1_release.wait()
            lock.release_read()
            with log_lock:
                log.append("r1-end")

        def writer1() -> None:
            r1_acquired.wait()
            # Increment writers_waiting before signalling w1_queued
            # so reader2 sees it immediately.
            with lock._condition:
                lock._writers_waiting += 1
                w1_queued.set()
                # Now properly acquire (will wait for r1 to release).
                while lock._readers_active > 0 or lock._writer_active:
                    lock._condition.wait()
                lock._writer_active = True
                lock._writers_waiting -= 1

            with log_lock:
                log.append("w1")
            with lock._condition:
                lock._writer_active = False
                lock._condition.notify_all()

        def reader2() -> None:
            w1_queued.wait()
            lock.acquire_read()
            with log_lock:
                log.append("r2")
            lock.release_read()

        t_r1 = threading.Thread(target=reader1, daemon=True)
        t_w1 = threading.Thread(target=writer1, daemon=True)
        t_r2 = threading.Thread(target=reader2, daemon=True)

        t_r1.start()
        r1_acquired.wait(timeout=2)
        t_w1.start()
        w1_queued.wait(timeout=2)
        t_r2.start()
        time.sleep(0.05)

        # Reader-2 must still be blocked.
        assert "r2" not in log, "Reader-2 entered before writer-1 (priority violated)"

        r1_release.set()
        for t in (t_r1, t_w1, t_r2):
            t.join(timeout=3)

        assert log.index("w1") < log.index("r2"), (
            f"Writer did not run before reader-2. log={log}"
        )

    def test_release_read_without_readers_raises_nothing(self) -> None:
        """release_read on a counter that is already 0 should not raise."""
        lock = ReadWriteLock()
        # Direct call to trigger the edge case in isolation.
        with lock._condition:
            lock._readers_active = 0
        # Should not raise even though it's a misuse.
        lock.release_read()

    def test_multiple_writers_serialised(self) -> None:
        """Concurrent writers must never overlap — each sees the previous result."""
        lock = ReadWriteLock()
        counter = [0]
        errors: list[str] = []
        N = 6

        def writer(expected: int) -> None:
            lock.acquire_write()
            try:
                if counter[0] != expected:
                    errors.append(f"Expected {expected}, got {counter[0]}")
                counter[0] += 1
            finally:
                lock.release_write()

        # Run writers in parallel; each expects to see the previous value.
        # Since execution order is non-deterministic, we just verify
        # the final count equals N and no interleaving occurred.
        threads = [threading.Thread(target=lambda: _write_inc(lock, counter, errors), daemon=True) for _ in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert counter[0] == N
        assert not errors, f"Race condition detected: {errors}"

def _write_inc(lock: ReadWriteLock, counter: list[int], errors: list[str]) -> None:
    lock.acquire_write()
    try:
        old = counter[0]
        time.sleep(0.001)  # Yield to other threads.
        if counter[0] != old:
            errors.append(f"Counter changed from {old} to {counter[0]} inside lock")
        counter[0] += 1
    finally:
        lock.release_write()


# ======================================================================
# Part 1 — GradeRepository unit tests
# ======================================================================

class TestGradeRepository:
    def test_write_and_read(self) -> None:
        repo = GradeRepository()
        r = GradeRecord(student_id="s1", course_id="C1", assignment_id="a1", score=88.5)
        repo.write_grade(r)
        result = repo.read_grade("s1", "C1")
        assert result is not None
        assert result.score == 88.5

    def test_read_nonexistent_returns_none(self) -> None:
        repo = GradeRepository()
        assert repo.read_grade("nobody", "MATH") is None

    def test_concurrent_writes_no_data_loss(self) -> None:
        """100 concurrent writers — every grade must be stored."""
        repo = GradeRepository()
        N = 100

        def write(i: int) -> None:
            repo.write_grade(
                GradeRecord(
                    student_id=f"s{i}",
                    course_id="TEST",
                    assignment_id=f"a{i}",
                    score=float(i),
                )
            )

        threads = [threading.Thread(target=write, args=(i,), daemon=True) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        grades = repo.all_grades()
        assert len(grades) == N

    def test_concurrent_reads_do_not_block_each_other(self) -> None:
        """N reader threads must all finish well within a tight timeout."""
        repo = GradeRepository()
        repo.write_grade(GradeRecord(student_id="s1", course_id="C1", assignment_id="a1", score=90.0))
        N = 20
        start = time.perf_counter()
        threads = [
            threading.Thread(
                target=lambda: repo.read_grade("s1", "C1"),
                daemon=True,
            )
            for _ in range(N)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)
        elapsed = time.perf_counter() - start
        # If reads were serialised they would each block ~0ms but in
        # pathological cases (lock contention) it could still be slow.
        # 1 second is a very generous limit for 20 in-memory reads.
        assert elapsed < 1.0, f"Reads took {elapsed:.3f}s — possible serialisation"


# ======================================================================
# Part 1 — AssignmentWorker unit tests
# ======================================================================

class TestAssignmentWorker:
    def test_worker_grades_single_assignment(self) -> None:
        repo = GradeRepository()
        q: queue.Queue[Assignment] = queue.Queue()
        stop = threading.Event()

        assignment = Assignment.new("student-01", "CS101", "My answer")
        q.put(assignment)

        worker = AssignmentWorker(
            worker_id="test",
            task_queue=q,
            repo=repo,
            stop_event=stop,
        )
        worker.start()
        q.join()          # Wait until assignment is processed.
        stop.set()
        worker.join(timeout=3)

        grade = repo.read_grade("student-01", "CS101")
        assert grade is not None
        assert 0.0 <= grade.score <= 100.0
        assert worker.graded_count == 1

    def test_three_workers_grade_all_assignments(self) -> None:
        repo = GradeRepository()
        q: queue.Queue[Assignment] = queue.Queue(maxsize=10)
        stop = threading.Event()

        workers = [
            AssignmentWorker(
                worker_id=str(i),
                task_queue=q,
                repo=repo,
                stop_event=stop,
            )
            for i in range(3)
        ]
        for w in workers:
            w.start()

        for i in range(15):
            q.put(Assignment.new(f"s{i:02d}", "MATH", f"answer {i}"))

        q.join()
        stop.set()
        for w in workers:
            w.join(timeout=5)

        grades = repo.all_grades()
        assert len(grades) == 15
        total = sum(w.graded_count for w in workers)
        assert total == 15

    def test_worker_stops_on_event(self) -> None:
        """Worker must exit within a reasonable time after stop_event is set."""
        repo = GradeRepository()
        q: queue.Queue[Assignment] = queue.Queue()
        stop = threading.Event()

        worker = AssignmentWorker(
            worker_id="stopper",
            task_queue=q,
            repo=repo,
            stop_event=stop,
        )
        worker.start()
        stop.set()
        worker.join(timeout=2)
        assert not worker.is_alive()


# ======================================================================
# Part 1 — ProducerConsumerService integration test
# ======================================================================

class TestProducerConsumerService:
    def test_all_assignments_graded(self) -> None:
        result = ProducerConsumerService().run()
        assert result.graded_assignments == result.total_assignments == 15

    def test_throughput_positive(self) -> None:
        result = ProducerConsumerService().run()
        assert result.throughput > 0

    def test_worker_counts_sum_to_total(self) -> None:
        result = ProducerConsumerService().run()
        assert sum(result.worker_counts.values()) == result.graded_assignments

    def test_all_grades_in_valid_range(self) -> None:
        result = ProducerConsumerService().run()
        for g in result.grades:
            assert 0.0 <= g.score <= 100.0, f"Score out of range: {g.score}"


# ======================================================================
# Part 2 — PaymentConfigRepository unit tests
# ======================================================================

class TestPaymentConfigRepository:
    def test_get_rate_returns_correct_value(self) -> None:
        repo = PaymentConfigRepository({"EUR": 1.08, "GBP": 1.27})
        assert repo.get_rate("EUR") == pytest.approx(1.08)
        assert repo.get_rate("GBP") == pytest.approx(1.27)
        assert repo.get_rate("JPY") is None

    def test_update_and_snapshot(self) -> None:
        repo = PaymentConfigRepository({"EUR": 1.0})
        repo.update_rates({"EUR": 1.10, "GBP": 1.30})
        snap = repo.snapshot()
        assert snap["EUR"] == pytest.approx(1.10)
        assert snap["GBP"] == pytest.approx(1.30)

    def test_concurrent_readers_and_writers(self) -> None:
        """10 readers + 2 writers must not corrupt the rates dict."""
        repo = PaymentConfigRepository({"USD": 1.0, "EUR": 1.05})
        errors: list[str] = []

        def reader(n: int) -> None:
            for _ in range(5):
                rate = repo.get_rate("EUR")
                if rate is not None and not (0.9 < rate < 1.5):
                    errors.append(f"Reader {n}: corrupted rate {rate}")
                time.sleep(random.uniform(0.001, 0.01))

        def writer(n: int) -> None:
            for _ in range(3):
                new_rate = round(random.uniform(1.0, 1.3), 4)
                repo.update_rates({"EUR": new_rate})
                time.sleep(0.05)

        threads = (
            [threading.Thread(target=reader, args=(i,), daemon=True) for i in range(10)]
            + [threading.Thread(target=writer, args=(i,), daemon=True) for i in range(2)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Data corruption detected: {errors}"


# ======================================================================
# Part 2 — ReadersWritersService integration test
# ======================================================================

class TestReadersWritersService:
    def test_all_reads_and_writes_completed(self) -> None:
        result = ReadersWritersService().run()
        expected_reads = ReadersWritersService.NUM_READERS * ReadersWritersService.READS_PER_READER
        expected_writes = ReadersWritersService.NUM_WRITERS * ReadersWritersService.WRITES_PER_WRITER
        assert result.total_reads == expected_reads
        assert result.total_writes == expected_writes

    def test_no_writer_starvation(self) -> None:
        """With writer-priority lock, writers must never be starved."""
        result = ReadersWritersService().run()
        assert not result.starvation_detected, (
            "Writer starvation detected — ReadWriteLock priority is not working"
        )

    def test_all_writers_completed_their_writes(self) -> None:
        result = ReadersWritersService().run()
        for s in result.writer_stats:
            assert s.writes_completed == ReadersWritersService.WRITES_PER_WRITER


# ======================================================================
# Part 3 — BarrierService integration test
# ======================================================================

class TestBarrierService:
    def test_all_students_recorded(self) -> None:
        result = BarrierService().run()
        assert len(result.student_records) == BarrierService.NUM_STUDENTS

    def test_all_students_started_simultaneously(self) -> None:
        """All start_time values must be within 50 ms of each other."""
        result = BarrierService().run()
        assert result.all_started_simultaneously, (
            f"Students did not start simultaneously — "
            f"records: {result.student_records}"
        )

    def test_all_students_arrived_before_starting(self) -> None:
        """Every student must have arrived before the exam started."""
        result = BarrierService().run()
        for r in result.student_records:
            assert r.arrival_time <= r.start_time, (
                f"{r.student_id} started before arriving"
            )

    def test_latest_arrival_triggers_release(self) -> None:
        """The last student to arrive should have near-zero wait time."""
        result = BarrierService().run()
        last = max(result.student_records, key=lambda r: r.arrival_time)
        wait = last.start_time - last.arrival_time
        # The last arrival releases the barrier immediately, so wait < 50ms.
        assert wait < 0.05, f"Last student waited {wait:.4f}s — unexpected"

    def test_barrier_blocks_early_arrivals(self) -> None:
        """The first student to arrive must wait > 0 s at the barrier."""
        result = BarrierService().run()
        first = min(result.student_records, key=lambda r: r.arrival_time)
        wait = first.start_time - first.arrival_time
        assert wait > 0, "First student did not wait at the barrier"
