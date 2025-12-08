"""SurrealDB connection module."""

import logging

import surrealdb
from singleton import Singleton
from surrealdb import AsyncSurreal

from .schema_generator import init_schema

AsyncSurrealConnection = (
    surrealdb.AsyncEmbeddedSurrealConnection
    | surrealdb.AsyncWsSurrealConnection
    | surrealdb.AsyncHttpSurrealConnection
)
logger = logging.getLogger(__name__)


class DatabaseManager(metaclass=Singleton):
    """Manages SurrealDB connections."""

    def __init__(
        self,
        surrealdb_uri: str,
        surrealdb_username: str,
        surrealdb_password: str,
        surrealdb_namespace: str,
        surrealdb_database: str,
    ) -> None:
        """
        Initialize the database manager.

        Args:
            surrealdb_uri: SurrealDB connection URI
            surrealdb_username: SurrealDB username for authentication
            surrealdb_password: SurrealDB password for authentication
            surrealdb_namespace: SurrealDB namespace to use
            surrealdb_database: SurrealDB database name to use

        """
        self.db: AsyncSurrealConnection | None = None
        self.surrealdb_uri = surrealdb_uri
        self.surrealdb_username = surrealdb_username
        self.surrealdb_password = surrealdb_password
        self.surrealdb_namespace = surrealdb_namespace
        self.surrealdb_database = surrealdb_database

    async def connect(self) -> None:
        """Initialize database connection."""
        self.db = AsyncSurreal(self.surrealdb_uri)
        await self.db.connect()
        await self.db.signin({
            "username": self.surrealdb_username,
            "password": self.surrealdb_password,
        })
        await self.db.use(
            self.surrealdb_namespace,
            self.surrealdb_database,
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
