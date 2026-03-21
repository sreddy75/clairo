"""In-process event bus for domain events.

Provides a simple publish-subscribe mechanism for domain events within
the application process. For distributed events, use Celery tasks.

Usage:
    from app.core.events import event_bus, DomainEvent

    # Define an event
    class UserCreated(DomainEvent):
        pass

    # Subscribe a handler
    @event_bus.subscribe("UserCreated")
    async def handle_user_created(event: DomainEvent) -> None:
        print(f"User created: {event.aggregate_id}")

    # Publish an event
    await event_bus.publish(UserCreated(
        aggregate_type="User",
        aggregate_id=str(user.id),
        payload={"email": user.email}
    ))
"""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base class for all domain events.

    Events are immutable records of something that happened in the domain.
    They should be past-tense and describe what occurred.

    Attributes:
        event_id: Unique identifier for this event instance.
        event_type: Type name of the event (auto-set from class name).
        occurred_at: When the event occurred.
        aggregate_type: Type of the entity that produced this event.
        aggregate_id: ID of the entity that produced this event.
        payload: Additional event-specific data.
    """

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str = Field(default="")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Set event_type from class name if not provided."""
        if not self.event_type:
            object.__setattr__(self, "event_type", self.__class__.__name__)


# Type alias for event handlers
EventHandler = Callable[[DomainEvent], Awaitable[None]] | Callable[[DomainEvent], None]


class EventBus:
    """In-process event bus for domain events.

    Supports both sync and async handlers. Handlers are executed concurrently
    for async handlers, with errors logged but not propagated to allow
    other handlers to complete.

    This is an in-process event bus. For distributed event processing,
    use Celery tasks or a dedicated message broker.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator to subscribe a handler to an event type.

        Args:
            event_type: The event type name to subscribe to.

        Returns:
            Decorator function that registers the handler.

        Example:
            @event_bus.subscribe("UserCreated")
            async def handle_user_created(event: DomainEvent) -> None:
                ...
        """

        def decorator(handler: EventHandler) -> EventHandler:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            return handler

        return decorator

    def add_handler(self, event_type: str, handler: EventHandler) -> None:
        """Add a handler for an event type programmatically.

        Args:
            event_type: The event type name to subscribe to.
            handler: The handler function to call.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def remove_handler(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler for an event type.

        Args:
            event_type: The event type name.
            handler: The handler function to remove.
        """
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all subscribed handlers.

        Handlers are executed concurrently. Errors in individual handlers
        are logged but don't prevent other handlers from executing.

        Args:
            event: The domain event to publish.
        """
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        # Separate sync and async handlers
        async_tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                async_handler = cast("Callable[[DomainEvent], Awaitable[None]]", handler)
                async_tasks.append(self._execute_async_handler(async_handler, event))
            else:
                sync_handler = cast("Callable[[DomainEvent], None]", handler)
                await self._execute_sync_handler(sync_handler, event)

        # Execute all async handlers concurrently
        if async_tasks:
            await asyncio.gather(*async_tasks, return_exceptions=True)

    async def _execute_async_handler(
        self, handler: Callable[[DomainEvent], Awaitable[None]], event: DomainEvent
    ) -> None:
        """Execute an async handler with error handling."""
        try:
            await handler(event)
        except Exception as e:
            # Log error but don't propagate to allow other handlers to complete
            # In production, use proper logging
            print(f"Error in event handler {handler.__name__}: {e}")

    async def _execute_sync_handler(
        self, handler: Callable[[DomainEvent], None], event: DomainEvent
    ) -> None:
        """Execute a sync handler with error handling."""
        try:
            handler(event)
        except Exception as e:
            # Log error but don't propagate
            print(f"Error in event handler {handler.__name__}: {e}")

    def clear(self) -> None:
        """Remove all handlers. Useful for testing."""
        self._handlers.clear()

    def get_handlers(self, event_type: str) -> list[EventHandler]:
        """Get all handlers for an event type. Useful for testing."""
        return self._handlers.get(event_type, []).copy()


# Global event bus singleton
event_bus = EventBus()
