from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.application.dtos import (
    CreateJobRequestDTO,
    CreateJobResponseDTO,
    JobStatusResponseDTO,
    RegisterWebhookRequestDTO,
    RegisterWebhookResponseDTO,
    TextResultDTO,
)
from app.application.errors import BatchTooLargeError, ForbiddenError, JobNotFoundError
from app.application.services import JobService, WebhookService
from app.domain.models import Job
from app.presentation.auth import get_current_user_id
from app.presentation.websocket_manager import WebSocketManager


def build_router(
    *,
    job_service_provider: callable,
    webhook_service_provider: callable,
    ws_manager: WebSocketManager,
    settings_provider: callable,
) -> APIRouter:
    router = APIRouter()

    def get_job_service() -> JobService:
        return job_service_provider()

    def get_webhook_service() -> WebhookService:
        return webhook_service_provider()

    def _check_ws_auth(*, websocket: WebSocket, expected_user_id: str) -> None:
        settings = settings_provider()
        x_user_id = websocket.headers.get("x-user-id")
        x_api_key = websocket.headers.get("x-api-key")

        if x_user_id != expected_user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")
        if settings.api_key is not None and x_api_key != settings.api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

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
                    error=t.error,
                )
                for t in job.texts
            ],
        )

    @router.post("/webhooks", response_model=RegisterWebhookResponseDTO)
    def register_webhook(
        payload: RegisterWebhookRequestDTO,
        user_id: str = Depends(get_current_user_id),
        webhook_service: WebhookService = Depends(get_webhook_service),
    ) -> RegisterWebhookResponseDTO:
        webhook_service.register_callback_url(user_id=user_id, callback_url=str(payload.callback_url))
        return RegisterWebhookResponseDTO(user_id=user_id, callback_url=payload.callback_url)

    @router.websocket("/ws/jobs/{user_id}")
    async def ws_jobs(websocket: WebSocket, user_id: str) -> None:
        _check_ws_auth(websocket=websocket, expected_user_id=user_id)
        await ws_manager.connect(user_id, websocket)
        try:
            while True:
                # Keep connection open; client may send pings.
                await websocket.receive_text()
        except WebSocketDisconnect:
            await ws_manager.disconnect(user_id, websocket)

    return router
