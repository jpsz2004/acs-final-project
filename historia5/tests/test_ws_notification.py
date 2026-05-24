import threading
import time

from fastapi.testclient import TestClient

from app.config import Settings
from app.presentation.app_factory import create_app


def test_websocket_receives_job_completed_notification() -> None:
    app = create_app(settings=Settings(worker_count=2, processing_delay_ms=5, api_key=None, queue_maxsize=0, public_base_url=None))

    with TestClient(app) as client:
        with client.websocket_connect("/ws/jobs/user-1", headers={"X-User-Id": "user-1"}) as ws:
            resp = client.post("/jobs", headers={"X-User-Id": "user-1"}, json={"texts": ["hola", "mundo"]})
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            received: dict | None = None

            def recv() -> None:
                nonlocal received
                received = ws.receive_json()

            t = threading.Thread(target=recv, daemon=True)
            t.start()
            t.join(timeout=2.0)

            assert received is not None
            assert received["type"] == "job_completed"
            assert received["job_id"] == job_id
            assert received["results_url"].endswith(f"/jobs/{job_id}")


def test_websocket_disconnect_does_not_crash() -> None:
    app = create_app(settings=Settings(worker_count=1, processing_delay_ms=1, api_key=None, queue_maxsize=0, public_base_url=None))

    with TestClient(app) as client:
        ws = client.websocket_connect("/ws/jobs/user-1", headers={"X-User-Id": "user-1"})
        ws.__enter__()
        ws.close()
        ws.__exit__(None, None, None)

        # Ensure API still works.
        resp = client.post("/jobs", headers={"X-User-Id": "user-1"}, json={"texts": ["hola"]})
        assert resp.status_code == 202

        deadline = time.time() + 2.0
        while time.time() < deadline:
            status = client.get(f"/jobs/{resp.json()['job_id']}", headers={"X-User-Id": "user-1"})
            if status.json()["status"] in ("completed", "failed"):
                break
            time.sleep(0.02)
