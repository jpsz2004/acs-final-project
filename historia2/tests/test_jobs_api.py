import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.presentation.app_factory import create_app


def create_token_for_user(client: TestClient, email: str, password: str) -> str:
    register_resp = client.post("/register", json={"email": email, "password": password})
    assert register_resp.status_code == 201
    return register_resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_rejects_more_than_100_texts() -> None:
    app = create_app(settings=Settings(worker_count=1, processing_delay_ms=1, api_key=None, queue_maxsize=0))
    with TestClient(app) as client:
        token = create_token_for_user(client, "user1@example.com", "secret123")
        resp = client.post(
            "/jobs",
            headers=auth_headers(token),
            json={"texts": ["x"] * 101},
        )
        assert resp.status_code == 400


def test_create_job_and_process_in_background() -> None:
    app = create_app(settings=Settings(worker_count=2, processing_delay_ms=5, api_key=None, queue_maxsize=0))
    with TestClient(app) as client:
        token = create_token_for_user(client, "user2@example.com", "secret123")
        resp = client.post(
            "/jobs",
            headers=auth_headers(token),
            json={"texts": ["hola", "mundo", "excelente"]},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        job_id = data["job_id"]

        deadline = time.time() + 2.0
        last_status = None
        while time.time() < deadline:
            status_resp = client.get(f"/jobs/{job_id}", headers=auth_headers(token))
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
        token_a = create_token_for_user(client, "owner@example.com", "secret123")
        token_b = create_token_for_user(client, "other@example.com", "secret123")

        resp = client.post(
            "/jobs",
            headers=auth_headers(token_a),
            json={"texts": ["hola"]},
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        forbidden = client.get(f"/jobs/{job_id}", headers=auth_headers(token_b))
        assert forbidden.status_code == 403
