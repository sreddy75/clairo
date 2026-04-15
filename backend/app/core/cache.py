"""Simple Redis key-value cache for short-lived API response caching.

Uses a new connection per call — suitable for infrequent, high-latency
operations like external Xero API calls. Not intended for hot paths.
"""

import json
import logging
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis.url, decode_responses=True)


async def cache_get(key: str) -> Any | None:
    """Return cached value for key, or None if missing/expired."""
    try:
        r = _get_redis()
        val = await r.get(key)
        await r.aclose()
        return json.loads(val) if val is not None else None
    except Exception:
        logger.debug("Cache get failed for key %s", key, exc_info=True)
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """Store value under key with TTL in seconds."""
    try:
        r = _get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
        await r.aclose()
    except Exception:
        logger.debug("Cache set failed for key %s", key, exc_info=True)


async def cache_delete(key: str) -> None:
    """Delete a cached key."""
    try:
        r = _get_redis()
        await r.delete(key)
        await r.aclose()
    except Exception:
        logger.debug("Cache delete failed for key %s", key, exc_info=True)
