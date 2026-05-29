"""
Tests for Historia 5 — WebSocket Notifications + JWT Auth.

All tests use the full JWT flow:
  1. POST /register  -> access_token
  2. Use token in Authorization: Bearer <token> for REST endpoints.
  3. Connect to WebSocket with ?token=<token> query param.
"""

from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.presentation.app_factory import create_app


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _settings(**overrides) -> Settings:
    defaults = dict(
        worker_count=2,
        processing_delay_ms=5,
        api_key=None,
        queue_maxsize=0,
        public_base_url=None,
        database_url=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _register(client: TestClient, email: str, password: str = "secret123") -> str:
    resp = client.post("/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user_id_from_token(token: str) -> str:
    import jwt as _jwt
    return _jwt.decode(token, options={"verify_signature": False})["sub"]


# ─────────────────────────────────────────────────────────────────────────────
# Auth endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_returns_token(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            resp = client.post("/register", json={"email": "a@test.com", "password": "secret123"})
            assert resp.status_code == 201
            assert "access_token" in resp.json()

    def test_duplicate_register_returns_409(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            client.post("/register", json={"email": "dup@test.com", "password": "secret123"})
            resp = client.post("/register", json={"email": "dup@test.com", "password": "secret123"})
            assert resp.status_code == 409

    def test_login_returns_token(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            client.post("/register", json={"email": "login@test.com", "password": "secret123"})
            resp = client.post("/login", json={"email": "login@test.com", "password": "secret123"})
            assert resp.status_code == 200
            assert "access_token" in resp.json()

    def test_wrong_password_returns_401(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            client.post("/register", json={"email": "wp@test.com", "password": "secret123"})
            resp = client.post("/login", json={"email": "wp@test.com", "password": "wrong"})
            assert resp.status_code == 401

    def test_protected_endpoint_without_token_returns_401(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            resp = client.post("/jobs", json={"texts": ["hola"]})
            assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Jobs endpoints
# ─────────────────────────────────────────────────────────────────────────────

class TestJobs:
    def test_rejects_more_than_100_texts(self) -> None:
        app = create_app(settings=_settings(worker_count=1, processing_delay_ms=1))
        with TestClient(app) as client:
            token = _register(client, "big@test.com")
            resp = client.post("/jobs", headers=_auth(token), json={"texts": ["x"] * 101})
            assert resp.status_code == 400

    def test_create_job_returns_202_with_pending_status(self) -> None:
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            token = _register(client, "create@test.com")
            resp = client.post("/jobs", headers=_auth(token), json={"texts": ["hola", "mundo"]})
            assert resp.status_code == 202
            assert resp.json()["status"] == "pending"

    def test_job_completes_in_background(self) -> None:
        app = create_app(settings=_settings(worker_count=2, processing_delay_ms=5))
        with TestClient(app) as client:
            token = _register(client, "bg@test.com")
            resp = client.post(
                "/jobs", headers=_auth(token), json={"texts": ["hola", "excelente", "malo"]}
            )
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            deadline = time.time() + 3.0
            last_status = None
            while time.time() < deadline:
                r = client.get(f"/jobs/{job_id}", headers=_auth(token))
                assert r.status_code == 200
                last_status = r.json()["status"]
                if last_status in ("completed", "failed"):
                    break
                time.sleep(0.02)

            assert last_status == "completed"

    def test_job_is_user_scoped(self) -> None:
        app = create_app(settings=_settings(worker_count=1, processing_delay_ms=1))
        with TestClient(app) as client:
            token_a = _register(client, "owner5@test.com")
            token_b = _register(client, "other5@test.com")

            resp = client.post("/jobs", headers=_auth(token_a), json={"texts": ["hola"]})
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            forbidden = client.get(f"/jobs/{job_id}", headers=_auth(token_b))
            assert forbidden.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — auth validation
# ─────────────────────────────────────────────────────────────────────────────

class TestWebSocketAuth:
    def test_ws_rejects_connection_without_token(self) -> None:
        """
        When no ?token is present, the server calls websocket.close(1008).
        TestClient raises WebSocketDisconnect with code 1008.
        """
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            try:
                with client.websocket_connect("/ws/jobs/some-user-id") as ws:
                    ws.receive_json()
                assert False, "Expected WebSocketDisconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1008

    def test_ws_rejects_invalid_token(self) -> None:
        """Malformed JWT must cause a 1008 close."""
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            try:
                with client.websocket_connect(
                    "/ws/jobs/some-user-id?token=not.a.valid.jwt"
                ) as ws:
                    ws.receive_json()
                assert False, "Expected WebSocketDisconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1008

    def test_ws_rejects_token_user_mismatch(self) -> None:
        """
        Token is valid JWT but its 'sub' does not match the user_id in the path.
        The server must close with 1008.
        """
        app = create_app(settings=_settings())
        with TestClient(app) as client:
            token = _register(client, "real@test.com")
            try:
                with client.websocket_connect(
                    f"/ws/jobs/completely-different-id?token={token}"
                ) as ws:
                    ws.receive_json()
                assert False, "Expected WebSocketDisconnect"
            except WebSocketDisconnect as exc:
                assert exc.code == 1008


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket — notification delivery
# ─────────────────────────────────────────────────────────────────────────────

class TestWebSocketNotifications:
    def test_receives_job_completed_notification(self) -> None:
        app = create_app(settings=_settings(worker_count=2, processing_delay_ms=5))

        with TestClient(app) as client:
            token = _register(client, "ws_notify@test.com")
            user_id = _user_id_from_token(token)

            with client.websocket_connect(f"/ws/jobs/{user_id}?token={token}") as ws:
                resp = client.post(
                    "/jobs",
                    headers=_auth(token),
                    json={"texts": ["hola", "mundo"]},
                )
                assert resp.status_code == 202
                job_id = resp.json()["job_id"]

                received: dict | None = None

                def recv() -> None:
                    nonlocal received
                    received = ws.receive_json()

                t = threading.Thread(target=recv, daemon=True)
                t.start()
                t.join(timeout=3.0)

                assert received is not None, "No notification received within timeout"
                assert received["type"] == "job_completed"
                assert received["job_id"] == job_id
                assert received["results_url"].endswith(f"/jobs/{job_id}")

    def test_event_fires_exactly_once(self) -> None:
        app = create_app(settings=_settings(worker_count=4, processing_delay_ms=1))

        with TestClient(app) as client:
            token = _register(client, "once@test.com")
            user_id = _user_id_from_token(token)

            notifications: list[dict] = []
            lock = threading.Lock()

            with client.websocket_connect(f"/ws/jobs/{user_id}?token={token}") as ws:
                resp = client.post(
                    "/jobs",
                    headers=_auth(token),
                    json={"texts": ["a", "b", "c", "d"]},
                )
                job_id = resp.json()["job_id"]

                def collect() -> None:
                    try:
                        while True:
                            msg = ws.receive_json()
                            with lock:
                                notifications.append(msg)
                    except Exception:
                        pass

                collector = threading.Thread(target=collect, daemon=True)
                collector.start()
                time.sleep(0.5)

            assert len([n for n in notifications if n.get("job_id") == job_id]) == 1, (
                f"Expected exactly 1 notification, got {notifications}"
            )

    def test_disconnect_does_not_crash_api(self) -> None:
        app = create_app(settings=_settings(worker_count=1, processing_delay_ms=1))

        with TestClient(app) as client:
            token = _register(client, "disc@test.com")
            user_id = _user_id_from_token(token)

            ws = client.websocket_connect(f"/ws/jobs/{user_id}?token={token}")
            ws.__enter__()
            ws.close()
            ws.__exit__(None, None, None)

            resp = client.post("/jobs", headers=_auth(token), json={"texts": ["hola"]})
            assert resp.status_code == 202

            job_id = resp.json()["job_id"]
            deadline = time.time() + 2.0
            while time.time() < deadline:
                r = client.get(f"/jobs/{job_id}", headers=_auth(token))
                if r.json()["status"] in ("completed", "failed"):
                    break
                time.sleep(0.02)