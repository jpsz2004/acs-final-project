from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.application.dtos import CreateJobRequestDTO, CreateJobResponseDTO, JobStatusResponseDTO, TextResultDTO
from app.application.errors import BatchTooLargeError, ForbiddenError, JobNotFoundError
from app.application.services import JobService
from app.domain.models import Job
from app.presentation.auth import get_current_user_id


def build_router(*, job_service_provider: callable) -> APIRouter:
    router = APIRouter()

    def get_job_service() -> JobService:
        return job_service_provider()

    @router.post("/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=CreateJobResponseDTO)
    def create_job(
        payload: CreateJobRequestDTO,
        user_id: str = Depends(get_current_user_id),
        job_service: JobService = Depends(get_job_service),
    ) -> CreateJobResponseDTO:
        try:
            job = job_service.create_job(user_id=user_id, texts=payload.texts)
        except BatchTooLargeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        # El contrato del endpoint indica status inicial "pending".
        return CreateJobResponseDTO(job_id=job.job_id, status="pending")

    @router.get("/jobs/{job_id}", response_model=JobStatusResponseDTO)
    def get_job_status(
        job_id: str,
        user_id: str = Depends(get_current_user_id),
        job_service: JobService = Depends(get_job_service),
    ) -> JobStatusResponseDTO:
        try:
            job: Job = job_service.get_job_for_user(job_id=job_id, user_id=user_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

        return JobStatusResponseDTO(
            job_id=job.job_id,
            user_id=job.user_id,
            status=job.status.value,
            total_texts=len(job.texts),
            processed_texts=job.processed_count(),
            results=[
                TextResultDTO(
                    text_id=t.text_id,
                    status=t.status.value,
                    language=t.language,
                    sentiment=t.sentiment,
                    error=t.error,
                )
                for t in job.texts
            ],
        )

    return router
