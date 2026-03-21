"""Redis pub/sub for sync progress events.

Publishes and subscribes to real-time sync progress updates via Redis pub/sub.
Used by SSE endpoints to stream progress to the frontend.

Channel naming: sync_progress:{connection_id}
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_channel_name(connection_id: UUID) -> str:
    """Get Redis pub/sub channel name for a connection."""
    return f"sync_progress:{connection_id}"


def _serialize_event(event_type: str, data: dict[str, Any]) -> str:
    """Serialize an event for Redis pub/sub."""
    return json.dumps({"event": event_type, "data": data}, default=str)


class SyncProgressPublisher:
    """Publishes sync progress events to Redis pub/sub.

    Used by Celery tasks to broadcast progress updates.
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self._redis = redis_client
        self._owns_redis = redis_client is None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            settings = get_settings()
            self._redis = redis.from_url(
                settings.redis.url,
                decode_responses=True,
            )
        return self._redis

    async def close(self) -> None:
        """Close Redis connection if we own it."""
        if self._owns_redis and self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def _publish(self, connection_id: UUID, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to the connection's channel."""
        try:
            r = await self._get_redis()
            channel = _get_channel_name(connection_id)
            message = _serialize_event(event_type, data)
            await r.publish(channel, message)
        except Exception:
            logger.exception("Failed to publish sync progress event: %s", event_type)

    async def publish_sync_started(
        self,
        connection_id: UUID,
        job_id: UUID,
        phase: int,
        total_entities: int,
    ) -> None:
        """Publish sync_started event."""
        await self._publish(
            connection_id,
            "sync_started",
            {
                "job_id": str(job_id),
                "phase": phase,
                "total_entities": total_entities,
            },
        )

    async def publish_entity_progress(
        self,
        connection_id: UUID,
        entity_type: str,
        status: str,
        records_processed: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        records_failed: int = 0,
    ) -> None:
        """Publish entity_progress event."""
        await self._publish(
            connection_id,
            "entity_progress",
            {
                "entity_type": entity_type,
                "status": status,
                "records_processed": records_processed,
                "records_created": records_created,
                "records_updated": records_updated,
                "records_failed": records_failed,
            },
        )

    async def publish_phase_complete(
        self,
        connection_id: UUID,
        phase: int,
        next_phase: int | None,
        entities_completed: int,
        records_processed: int,
    ) -> None:
        """Publish phase_complete event."""
        await self._publish(
            connection_id,
            "phase_complete",
            {
                "phase": phase,
                "next_phase": next_phase,
                "entities_completed": entities_completed,
                "records_processed": records_processed,
            },
        )

    async def publish_sync_complete(
        self,
        connection_id: UUID,
        job_id: UUID,
        status: str,
        records_processed: int,
        records_created: int,
        records_updated: int,
        records_failed: int,
    ) -> None:
        """Publish sync_complete event."""
        await self._publish(
            connection_id,
            "sync_complete",
            {
                "job_id": str(job_id),
                "status": status,
                "records_processed": records_processed,
                "records_created": records_created,
                "records_updated": records_updated,
                "records_failed": records_failed,
            },
        )

    async def publish_sync_failed(
        self,
        connection_id: UUID,
        job_id: UUID,
        error: str,
        entity_type: str | None = None,
    ) -> None:
        """Publish sync_failed event."""
        await self._publish(
            connection_id,
            "sync_failed",
            {
                "job_id": str(job_id),
                "error": error,
                "entity_type": entity_type,
            },
        )

    async def publish_post_sync_progress(
        self,
        connection_id: UUID,
        task_type: str,
        status: str,
        result_summary: dict[str, Any] | None = None,
    ) -> None:
        """Publish post_sync_progress event."""
        await self._publish(
            connection_id,
            "post_sync_progress",
            {
                "task_type": task_type,
                "status": status,
                "result_summary": result_summary,
            },
        )


class SyncProgressSubscriber:
    """Subscribes to sync progress events from Redis pub/sub.

    Used by SSE endpoints to stream progress to the frontend.
    """

    def __init__(self, connection_id: UUID, job_id: UUID | None = None):
        self.connection_id = connection_id
        self.job_id = str(job_id) if job_id else None
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None

    async def _connect(self) -> None:
        """Connect to Redis and subscribe to channel."""
        settings = get_settings()
        self._redis = redis.from_url(
            settings.redis.url,
            decode_responses=True,
        )
        self._pubsub = self._redis.pubsub()
        channel = _get_channel_name(self.connection_id)
        await self._pubsub.subscribe(channel)

    async def close(self) -> None:
        """Unsubscribe and close Redis connection."""
        if self._pubsub is not None:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def listen(self) -> AsyncGenerator[str, None]:
        """Async generator yielding SSE-formatted event strings.

        Yields strings in SSE format:
            event: {event_type}\\ndata: {json_data}\\n\\n

        Filters by job_id if specified.
        """
        if self._pubsub is None:
            await self._connect()

        assert self._pubsub is not None

        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    payload = json.loads(message["data"])
                    event_type = payload.get("event", "unknown")
                    data = payload.get("data", {})

                    # Filter by job_id if specified
                    if self.job_id and data.get("job_id") and data["job_id"] != self.job_id:
                        continue

                    yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

                    # Stop on terminal events
                    if event_type in ("sync_complete", "sync_failed"):
                        break

                except (json.JSONDecodeError, KeyError):
                    logger.warning("Invalid sync progress message: %s", message["data"])
                    continue
        finally:
            await self.close()
