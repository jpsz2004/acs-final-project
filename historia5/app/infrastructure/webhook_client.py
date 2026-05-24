from __future__ import annotations

from typing import Protocol

import httpx


class WebhookClient(Protocol):
    def post_json(self, *, url: str, payload: dict) -> None: ...


class HttpxWebhookClient:
    def __init__(self, *, timeout_s: float = 3.0) -> None:
        self._timeout = timeout_s

    def post_json(self, *, url: str, payload: dict) -> None:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
