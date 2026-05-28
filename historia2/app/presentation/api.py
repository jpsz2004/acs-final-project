from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.application.dtos import (
    AuthResponseDTO,
    CreateJobRequestDTO,
    CreateJobResponseDTO,
    JobResultsResponseDTO,
    JobStatusResponseDTO,
    LoginRequestDTO,
    RegisterRequestDTO,
    ReportDTO,
    TextResultDTO,
)
from app.application.errors import (
    AuthenticationError,
    BatchTooLargeError,
    ForbiddenError,
    JobNotFoundError,
    UserAlreadyExistsError,
)
from app.application.services import AuthService, JobService, ReportService
from app.domain.models import Job
from app.presentation.auth import get_current_user_id


def build_router(
    *,
    job_service_provider: callable,
    auth_service_provider: callable,
    report_service_provider: callable,
) -> APIRouter:
    router = APIRouter()

    def get_job_service() -> JobService:
        return job_service_provider()

    def get_auth_service() -> AuthService:
        return auth_service_provider()

    def get_report_service() -> ReportService:
        return report_service_provider()

    @router.post("/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponseDTO)
    def register(payload: RegisterRequestDTO, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponseDTO:
        try:
            token = auth_service.register(email=payload.email, password=payload.password)
        except UserAlreadyExistsError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

        return AuthResponseDTO(access_token=token)

    @router.post("/login", response_model=AuthResponseDTO)
    def login(payload: LoginRequestDTO, auth_service: AuthService = Depends(get_auth_service)) -> AuthResponseDTO:
        try:
            token = auth_service.login(email=payload.email, password=payload.password)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        return AuthResponseDTO(access_token=token)

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
                    score=t.score,
                    error=t.error,
                )
                for t in job.texts
            ],
        )

    @router.get("/jobs/{job_id}/results", response_model=JobResultsResponseDTO)
    def get_job_results(
        job_id: str,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
        user_id: str = Depends(get_current_user_id),
        job_service: JobService = Depends(get_job_service),
    ) -> JobResultsResponseDTO:
        try:
            job, results = job_service.get_job_results(job_id=job_id, user_id=user_id, limit=limit, offset=offset)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

        return JobResultsResponseDTO(
            job_id=job.job_id,
            total_texts=len(job.texts),
            limit=limit,
            offset=offset,
            results=[
                TextResultDTO(
                    text_id=t.text_id,
                    status=t.status.value,
                    language=t.language,
                    sentiment=t.sentiment,
                    score=t.score,
                    error=t.error,
                )
                for t in results
            ],
        )

    @router.get("/jobs/{job_id}/report", response_model=ReportDTO)
    def get_job_report(
        job_id: str,
        user_id: str = Depends(get_current_user_id),
        report_service: ReportService = Depends(get_report_service),
    ) -> ReportDTO:
        try:
            report = report_service.get_report(job_id=job_id, user_id=user_id)
        except JobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
        except ForbiddenError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

        return ReportDTO(**report)

    return router
