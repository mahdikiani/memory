"""SurrealDB connection module."""

import logging

import surrealdb
from fastapi_mongo_base.core import db
from singleton import Singleton
from surrealdb import AsyncSurreal

from . import config
from .schema_generator import init_schema

AsyncSurrealConnection = (
    surrealdb.AsyncEmbeddedSurrealConnection
    | surrealdb.AsyncWsSurrealConnection
    | surrealdb.AsyncHttpSurrealConnection
)
logger = logging.getLogger(__name__)


class DatabaseManager(metaclass=Singleton):
    """Manages SurrealDB connections."""

    def __init__(self, settings: config.Settings) -> None:
        """
        Initialize the database manager.

        Args:
            settings: The settings for the database manager.

        """
        self.db: AsyncSurrealConnection | None = None
        self.settings = settings

    async def connect(self) -> None:
        """Initialize database connection."""
        self.db = AsyncSurreal(self.settings.surrealdb_uri)
        await self.db.connect()
        await self.db.signin({
            "username": self.settings.surrealdb_username,
            "password": self.settings.surrealdb_password,
        })
        await self.db.use(
            self.settings.surrealdb_namespace,
            self.settings.surrealdb_database,
        )

    async def init_schema(self) -> None:
        """Initialize schema from Pydantic models."""
        await init_schema(self.db)

    async def disconnect(self) -> None:
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None

    def get_db(self) -> AsyncSurrealConnection:
        """Get the database connection."""
        if not self.db:
            raise RuntimeError("Database not connected")
        return self.db


# Global database manager instance
db_manager = DatabaseManager(config.Settings())


redis, redis_sync = db.init_redis()
