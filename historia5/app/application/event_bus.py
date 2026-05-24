from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

TEvent = TypeVar("TEvent")


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: dict[type, list[Callable[[Any], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: Callable[[TEvent], None]) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)  # type: ignore[arg-type]

    def publish(self, event: Any) -> None:
        with self._lock:
            handlers = list(self._handlers.get(type(event), []))

        for handler in handlers:
            handler(event)
