"""
Historia 8 — LMS Platform: main entry point.

Runs all three concurrency simulations sequentially and prints a
structured summary to stdout.  Each section is clearly delimited
so the output is easy to read and demonstrate to a professor.

Usage
-----
From the historia8/ directory:

    python -m app.main

Or directly:

    python app/main.py

Logging
-------
Set the LOG_LEVEL environment variable to control verbosity:
    LOG_LEVEL=DEBUG python -m app.main   <- shows every lock event
    LOG_LEVEL=INFO  python -m app.main   <- default (per-task events)
    LOG_LEVEL=WARNING python -m app.main <- summary only
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

from app.application.services import (
    BarrierService,
    ProducerConsumerService,
    ReadersWritersService,
)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
#
# Problem: logging.basicConfig's datefmt is passed to time.strftime(), which
# does NOT support %f (microseconds) on Windows — that specifier only works
# in datetime.strftime().  The fix is a custom Formatter that builds the
# timestamp with datetime directly, giving cross-platform millisecond output.

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class _MsFormatter(logging.Formatter):
    """Timestamp formatter with milliseconds — works on Windows and Linux."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        # datetime.strftime supports %f (microseconds) everywhere.
        return datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(_MsFormatter("%(asctime)s  %(threadName)-20s  %(message)s"))
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    handlers=[_handler],
)
logger = logging.getLogger(__name__)

SEP = "=" * 70


def _header(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def run_part1() -> None:
    _header("PART 1 -- Producer-Consumer (LMS Grading)")
    print("  15 students submit assignments -> 3 workers grade concurrently")
    print(f"  Queue capacity: {ProducerConsumerService.QUEUE_CAPACITY} slots\n")

    result = ProducerConsumerService().run()

    print(f"\n{'─' * 70}")
    print("  RESULTS -- Part 1")
    print(f"{'─' * 70}")
    print(f"  Total assignments  : {result.total_assignments}")
    print(f"  Graded assignments : {result.graded_assignments}")
    print(f"  Elapsed time       : {result.elapsed_seconds:.3f} s")
    print(f"  Throughput         : {result.throughput:.3f} assignments/s")
    print()
    print("  Worker breakdown:")
    for name, count in sorted(result.worker_counts.items()):
        print(f"    {name:25s}  ->  {count} graded")
    print()
    print("  Sample grades (first 5):")
    for g in result.grades[:5]:
        print(f"    {g.student_id}  {g.course_id}  ->  {g.score:.2f}")


def run_part2() -> None:
    _header("PART 2 -- Readers-Writers (Grade Access Control)")
    print("  10 student readers (5 reads each) + 2 professor writers (3 writes each)")
    print("  ReadWriteLock with WRITER PRIORITY -- writers never starve\n")

    result = ReadersWritersService().run()

    print(f"\n{'─' * 70}")
    print("  RESULTS -- Part 2")
    print(f"{'─' * 70}")
    print(f"  Elapsed time    : {result.elapsed_seconds:.3f} s")
    print(f"  Total reads     : {result.total_reads}")
    print(f"  Total writes    : {result.total_writes}")
    print()
    print("  Writer statistics:")
    for s in result.writer_stats:
        starved_label = "STARVED" if s.was_starved else "OK"
        print(
            f"    Writer {s.writer_id:4s}  "
            f"writes={s.writes_completed}  "
            f"starvation={starved_label}"
        )
    starvation_label = (
        "YES -- review lock implementation"
        if result.starvation_detected
        else "No writer starvation detected"
    )
    print(f"\n  Starvation detected: {starvation_label}")


def run_part3() -> None:
    _header("PART 3 -- Barrier (Synchronised Exam Start)")
    print(f"  {BarrierService.NUM_STUDENTS} students connect at random times")
    print("  threading.Barrier releases all simultaneously\n")

    result = BarrierService().run()

    print(f"\n{'─' * 70}")
    print("  RESULTS -- Part 3")
    print(f"{'─' * 70}")
    print(f"  Elapsed time         : {result.elapsed_seconds:.3f} s")
    print(f"  Max wait at barrier  : {result.max_wait_seconds:.4f} s")
    simultaneous_label = (
        "All students started within 50 ms"
        if result.all_started_simultaneously
        else "Spread > 50 ms -- check Barrier implementation"
    )
    print(f"  Simultaneous start   : {simultaneous_label}")
    print()
    print("  Student timeline:")
    print(f"    {'Student':<12} {'Arrived at':>12} {'Started at':>12} {'Wait':>10}")
    print(f"    {'─' * 50}")
    for r in result.student_records:
        wait = r.start_time - r.arrival_time
        print(
            f"    {r.student_id:<12} {r.arrival_time:>10.3f}s "
            f"{r.start_time:>10.3f}s  {wait:>8.4f}s"
        )


def main() -> None:
    print(SEP)
    print("  Historia 8 -- LMS Platform - Concurrency Simulations")
    print("  IS924 ACS -- Universidad Tecnologica de Pereira")
    print(SEP)

    run_part1()
    run_part2()
    run_part3()

    print(f"\n{SEP}")
    print("  All simulations completed.")
    print(SEP)


if __name__ == "__main__":
    main()