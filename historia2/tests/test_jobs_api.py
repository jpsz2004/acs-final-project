import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.presentation.app_factory import create_app


def test_rejects_more_than_100_texts() -> None:
    app = create_app(settings=Settings(worker_count=1, processing_delay_ms=1, api_key=None, queue_maxsize=0))
    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            headers={"X-User-Id": "user-1"},
            json={"texts": ["x"] * 101},
        )
        assert resp.status_code == 400


def test_create_job_and_process_in_background() -> None:
    app = create_app(settings=Settings(worker_count=2, processing_delay_ms=5, api_key=None, queue_maxsize=0))
    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            headers={"X-User-Id": "user-1"},
            json={"texts": ["hola", "mundo", "excelente"]},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        job_id = data["job_id"]

        deadline = time.time() + 2.0
        last_status = None
        while time.time() < deadline:
            status_resp = client.get(f"/jobs/{job_id}", headers={"X-User-Id": "user-1"})
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            last_status = status_data["status"]
            if last_status in ("completed", "failed"):
                break
            time.sleep(0.02)

        assert last_status == "completed"


def test_job_is_user_scoped() -> None:
    app = create_app(settings=Settings(worker_count=1, processing_delay_ms=1, api_key=None, queue_maxsize=0))
    with TestClient(app) as client:
        resp = client.post(
            "/jobs",
            headers={"X-User-Id": "user-1"},
            json={"texts": ["hola"]},
        )
        job_id = resp.json()["job_id"]

        forbidden = client.get(f"/jobs/{job_id}", headers={"X-User-Id": "user-2"})
        assert forbidden.status_code == 403
