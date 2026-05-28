from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import uuid4


class InvalidEmailError(ValueError):
    pass


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TextStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
            raise InvalidEmailError("Invalid email address")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True)
class Password:
    hashed: str


@dataclass
class User:
    user_id: str
    email: Email
    password: Password

    @staticmethod
    def new(email: Email, password: Password) -> "User":
        return User(user_id=str(uuid4()), email=email, password=password)


@dataclass
class Text:
    text_id: str
    content: str
    language: Optional[str] = None
    sentiment: Optional[str] = None
    score: float = 0.0
    status: TextStatus = TextStatus.pending
    error: Optional[str] = None


@dataclass
class Job:
    job_id: str
    user_id: str
    status: JobStatus
    texts: list[Text] = field(default_factory=list)

    @staticmethod
    def new(user_id: str, texts: list[str]) -> "Job":
        job_id = str(uuid4())
        text_entities = [Text(text_id=str(uuid4()), content=content) for content in texts]
        return Job(job_id=job_id, user_id=user_id, status=JobStatus.pending, texts=text_entities)

    def processed_count(self) -> int:
        return sum(1 for t in self.texts if t.status in (TextStatus.completed, TextStatus.failed))
