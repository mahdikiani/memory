"""Generic Redis queue manager (LPUSH / BRPOP)."""

import json
import logging

from server import config
from server.db import redis

logger = logging.getLogger(__name__)


def _get_queue_name(queue_name: str | None = None) -> str:
    settings = config.Settings()
    return queue_name or getattr(settings, "redis_queue_name", "default:queue")


async def enqueue(payload: dict[str, object], queue_name: str | None = None) -> int:
    """Push a JSON payload to Redis list (LPUSH)."""
    if redis is None:
        raise RuntimeError("Redis is not configured; cannot enqueue")

    target_queue = _get_queue_name(queue_name)
    index = await redis.lpush(target_queue, json.dumps(payload, ensure_ascii=False))
    logger.info("Enqueued message %s to %s", payload.get("job_id"), target_queue)
    return index


async def dequeue(
    queue_name: str | None = None, block_timeout: int = 5
) -> dict[str, object] | None:
    """Blocking pop from Redis list (BRPOP)."""
    if redis is None:
        raise RuntimeError("Redis is not configured; cannot dequeue")

    target_queue = _get_queue_name(queue_name)
    result = await redis.brpop(target_queue, timeout=block_timeout)
    if not result:
        return None

    _, raw = result
    try:
        return json.loads(raw)
    except Exception:
        logger.exception("Failed to decode dequeued payload")

    return None
