"""SurrealDB connection module."""

import logging

from db.manager import DatabaseManager

from . import config

logger = logging.getLogger(__name__)


def init_redis(settings: config.Settings | None = None) -> tuple:
    """
    Initialize the Redis connection.

    Args:
        settings: The settings for the Redis connection.

    Returns:
        A tuple containing the Redis and RedisSync instances.

    Raises:
        Exception: If there is an error initializing the Redis connection.
    """
    try:
        from redis import Redis as RedisSync
        from redis.asyncio.client import Redis

        if settings is None:
            settings = config.Settings()

        redis_uri = getattr(settings, "redis_uri", None)
        if redis_uri:
            redis_sync: RedisSync = RedisSync.from_url(redis_uri)
            redis: Redis = Redis.from_url(redis_uri)

            return redis_sync, redis
    except (ImportError, AttributeError, Exception):
        logging.exception("Error initializing Redis")

    return None, None


# Global database manager instance
db_manager = DatabaseManager(
    config.Settings().surrealdb_uri,
    config.Settings().surrealdb_username,
    config.Settings().surrealdb_password,
    config.Settings().surrealdb_namespace,
    config.Settings().surrealdb_database,
)

redis, redis_sync = init_redis()
