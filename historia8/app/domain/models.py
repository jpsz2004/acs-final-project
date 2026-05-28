"""
Domain models for Historia 8 — LMS Platform.

These entities represent the core business concepts:
- Assignment: a task submitted by a student for grading.
- Grade: the result produced by a worker after evaluating an assignment.
- ExchangeRate: a currency rate read/written by the payment simulation (Part 2).

All classes are plain dataclasses with no framework dependencies,
following the Clean Architecture principle that the domain layer
must remain isolated from infrastructure concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class AssignmentStatus(str, Enum):
    pending = "pending"
    grading = "grading"
    graded = "graded"


@dataclass
class Assignment:
    """Represents a student's submission waiting to be graded."""

    assignment_id: str
    student_id: str
    course_id: str
    answer_text: str
    status: AssignmentStatus = AssignmentStatus.pending
    grade: float | None = None  # 0.0 – 100.0

    @staticmethod
    def new(student_id: str, course_id: str, answer_text: str) -> "Assignment":
        return Assignment(
            assignment_id=str(uuid4()),
            student_id=student_id,
            course_id=course_id,
            answer_text=answer_text,
        )


@dataclass
class GradeRecord:
    """Immutable result stored after an assignment is evaluated."""

    student_id: str
    course_id: str
    assignment_id: str
    score: float  # 0.0 – 100.0


@dataclass
class ExchangeRate:
    """
    Currency exchange rate (used in the Readers-Writers simulation).
    Maps a currency code (e.g. 'EUR') to its USD rate.
    """

    currency: str
    rate: float  # USD equivalent of 1 unit of `currency`
