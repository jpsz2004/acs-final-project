from __future__ import annotations

from pydantic import BaseModel, Field


class CreateJobRequestDTO(BaseModel):
    texts: list[str] = Field(..., description="Batch of texts to analyze", examples=[["hola", "mundo"]])


class CreateJobResponseDTO(BaseModel):
    job_id: str
    status: str


class TextResultDTO(BaseModel):
    text_id: str
    status: str
    language: str | None = None
    sentiment: str | None = None
    score: float | None = None
    error: str | None = None


class JobStatusResponseDTO(BaseModel):
    job_id: str
    user_id: str
    status: str
    total_texts: int
    processed_texts: int
    results: list[TextResultDTO]


class JobResultsResponseDTO(BaseModel):
    job_id: str
    total_texts: int
    limit: int
    offset: int
    results: list[TextResultDTO]


class ReportDTO(BaseModel):
    job_id: str
    total_texts: int
    processed_texts: int
    completed_texts: int
    failed_texts: int
    average_score: float


class RegisterRequestDTO(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(..., min_length=6)


class LoginRequestDTO(BaseModel):
    email: str
    password: str


class AuthResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
