"""
Domain models for Historia 5 — pure Python, no framework dependencies.

These are the core business entities. No SQLAlchemy, no FastAPI, no Pydantic.
The infrastructure layer (models.py ORM) maps these to database rows.

Entities
--------
- User       : authenticated user identified by email (unique).
- Job        : a batch of texts submitted for sentiment analysis.
- Text       : a single text within a Job, with its analysis result.

Value Objects
-------------
- Email      : validated, normalised email address.
- Password   : wrapper around a bcrypt hash — never stores plaintext.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class InvalidEmailError(ValueError):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


class TextStatus(str, Enum):
    pending    = "pending"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


# ── Value Objects ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Email:
    """
    Validated, lower-cased email address.

    Raises InvalidEmailError on construction if the format is invalid.
    Uses object.__setattr__ to mutate the frozen dataclass during __post_init__
    so that the stored value is always normalised.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise InvalidEmailError(f"Invalid email address: {self.value!r}")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class Password:
    """Wraps a bcrypt hash. Never holds plaintext."""
    hashed: str


# ── Entities ──────────────────────────────────────────────────────────────────

@dataclass
class User:
    user_id:  str
    email:    Email
    password: Password

    @staticmethod
    def new(email: Email, password: Password) -> "User":
        return User(user_id=str(uuid4()), email=email, password=password)


@dataclass
class Text:
    text_id:   str
    content:   str
    language:  Optional[str]   = None
    sentiment: Optional[str]   = None
    score:     float           = 0.0
    status:    TextStatus      = TextStatus.pending
    error:     Optional[str]   = None


@dataclass
class Job:
    job_id:  str
    user_id: str
    status:  JobStatus
    texts:   list[Text] = field(default_factory=list)

    @staticmethod
    def new(user_id: str, texts: list[str]) -> "Job":
        job_id = str(uuid4())
        text_entities = [
            Text(text_id=str(uuid4()), content=content)
            for content in texts
        ]
        return Job(
            job_id=job_id,
            user_id=user_id,
            status=JobStatus.pending,
            texts=text_entities,
        )

    def processed_count(self) -> int:
        return sum(
            1 for t in self.texts
            if t.status in (TextStatus.completed, TextStatus.failed)
        )