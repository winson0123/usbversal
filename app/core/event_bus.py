"""In-process event bus for job and scan notifications."""

from collections.abc import Callable
from typing import Any

import structlog

from app.core.event_envelope import Event, wrap_event

logger = structlog.get_logger(__name__)

EventHandler = Callable[[Event], None]


class EventBus:
    """
    Synchronous publish/subscribe bus for structured events.

    Subscribers receive normalized ``Event`` envelopes. Subscriber failures
    are logged and ignored.
    """

    def __init__(self) -> None:
        """Initialize an empty subscriber list."""
        self._subscribers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        """
        Register an event handler.

        Args:
            handler: Callable invoked for each published Event envelope.
        """
        self._subscribers.append(handler)

    def publish(self, event: Any) -> None:
        """
        Dispatch an event to all subscribers as a normalized envelope.

        Args:
            event: Event dataclass or pre-built Event envelope.
        """
        envelope = wrap_event(event)
        for handler in self._subscribers:
            try:
                handler(envelope)
            except Exception:
                logger.exception(
                    "event_subscriber_failed",
                    event_type=envelope.type,
                )
