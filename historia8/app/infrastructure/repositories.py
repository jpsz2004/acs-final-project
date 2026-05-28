"""
Thread-safe repositories for Historia 8.

GradeRepository
---------------
Stores GradeRecord objects indexed by (student_id, course_id).

Uses a ReadWriteLock so:
- Multiple student threads can read grades simultaneously.
- A professor thread writing a grade gets exclusive access.
- Writers are never starved by a flood of readers.

PaymentConfigRepository
-----------------------
Stores currency exchange rates (currency → USD rate).
Uses the same ReadWriteLock strategy for the Readers-Writers
simulation in Part 2.
"""

from __future__ import annotations

import threading

from app.domain.models import GradeRecord
from app.infrastructure.locks import ReadWriteLock


class GradeRepository:
    """
    In-memory store for student grades.

    Thread-safety contract
    ----------------------
    - read_grade()  → acquires read lock  (concurrent reads allowed).
    - write_grade() → acquires write lock (exclusive, writer-priority).
    """

    def __init__(self) -> None:
        self._lock = ReadWriteLock()
        # key: (student_id, course_id) → GradeRecord
        self._grades: dict[tuple[str, str], GradeRecord] = {}

    # ------------------------------------------------------------------
    # Readers
    # ------------------------------------------------------------------

    def read_grade(self, student_id: str, course_id: str) -> GradeRecord | None:
        """Return the grade for a student/course pair, or None if absent."""
        self._lock.acquire_read()
        try:
            return self._grades.get((student_id, course_id))
        finally:
            self._lock.release_read()

    def all_grades(self) -> list[GradeRecord]:
        """Return a snapshot of all stored grades."""
        self._lock.acquire_read()
        try:
            return list(self._grades.values())
        finally:
            self._lock.release_read()

    # ------------------------------------------------------------------
    # Writers
    # ------------------------------------------------------------------

    def write_grade(self, record: GradeRecord) -> None:
        """Store or overwrite a grade record (exclusive write)."""
        self._lock.acquire_write()
        try:
            self._grades[(record.student_id, record.course_id)] = record
        finally:
            self._lock.release_write()


class PaymentConfigRepository:
    """
    In-memory store for currency exchange rates.

    Used in Part 2 to simulate 10 readers (processors) and
    2 writers (external rate service) with writer priority.
    """

    def __init__(self, initial_rates: dict[str, float] | None = None) -> None:
        self._lock = ReadWriteLock()
        self._rates: dict[str, float] = dict(initial_rates or {})

    def get_rate(self, currency: str) -> float | None:
        """Read the USD rate for a currency (concurrent reads allowed)."""
        self._lock.acquire_read()
        try:
            return self._rates.get(currency)
        finally:
            self._lock.release_read()

    def update_rates(self, rates: dict[str, float]) -> None:
        """Replace one or more rates (exclusive write)."""
        self._lock.acquire_write()
        try:
            self._rates.update(rates)
        finally:
            self._lock.release_write()

    def snapshot(self) -> dict[str, float]:
        """Return a full snapshot of current rates (read lock)."""
        self._lock.acquire_read()
        try:
            return dict(self._rates)
        finally:
            self._lock.release_read()
