"""In-process event bus for job and scan notifications."""

from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

EventHandler = Callable[[Any], None]


class EventBus:
    """
    Synchronous publish/subscribe bus for structured events.

    Subscribers must not raise; failures are logged and ignored.
    """

    def __init__(self) -> None:
        """Initialize an empty subscriber list."""
        self._subscribers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """
        Register an event handler.

        Args:
            handler: Callable invoked for each published event.
        """
        self._subscribers.append(handler)

    def publish(self, event: Any) -> None:
        """
        Dispatch an event to all subscribers.

        Args:
            event: Event dataclass or other payload.
        """
        for handler in self._subscribers:
            try:
                handler(event)
            except Exception:
                logger.exception(
                    "event_subscriber_failed",
                    event_type=type(event).__name__,
                )
