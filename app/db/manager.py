"""SurrealDB connection module."""

import logging

import surrealdb
from singleton import Singleton

AsyncSurrealConnection = (
    surrealdb.AsyncEmbeddedSurrealConnection
    | surrealdb.AsyncWsSurrealConnection
    | surrealdb.AsyncHttpSurrealConnection
)
BlockingSurrealConnection = (
    surrealdb.BlockingEmbeddedSurrealConnection
    | surrealdb.BlockingWsSurrealConnection
    | surrealdb.BlockingHttpSurrealConnection
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
        self.async_db: AsyncSurrealConnection | None = None
        self.blocking_db: BlockingSurrealConnection | None = None
        self.surrealdb_uri = surrealdb_uri
        self.surrealdb_username = surrealdb_username
        self.surrealdb_password = surrealdb_password
        self.surrealdb_namespace = surrealdb_namespace
        self.surrealdb_database = surrealdb_database

    async def aconnect(self) -> None:
        """Initialize database connection."""
        self.async_db = surrealdb.AsyncSurreal(self.surrealdb_uri)
        await self.async_db.connect()
        await self.async_db.signin({
            "username": self.surrealdb_username,
            "password": self.surrealdb_password,
        })
        await self.async_db.use(
            self.surrealdb_namespace,
            self.surrealdb_database,
        )

    async def ainit_schema(self) -> None:
        """Initialize schema from Pydantic models."""
        from .schema_generator import init_schema

        await init_schema(self.async_db)

    async def adisconnect(self) -> None:
        """Close database connection."""
        if self.async_db:
            await self.async_db.close()
            self.async_db = None

    def get_async_db(self) -> AsyncSurrealConnection:
        """Get the async database connection."""
        if not self.async_db:
            raise RuntimeError("Database not connected")
        return self.async_db

    def get_db(self) -> AsyncSurrealConnection:
        """Get the database connection."""

        return self.get_async_db()

    def get_blocking_db(self) -> BlockingSurrealConnection:
        """Get the blocking database connection."""
        if not self.blocking_db:
            raise RuntimeError("Database not connected")
        return self.blocking_db

    def connect(self) -> None:
        """Connect to the database."""
        self.blocking_db = surrealdb.Surreal(self.surrealdb_uri)
        self.blocking_db.connect()
        self.blocking_db.signin({
            "username": self.surrealdb_username,
            "password": self.surrealdb_password,
        })
        self.blocking_db.use(
            self.surrealdb_namespace,
            self.surrealdb_database,
        )

    def disconnect(self) -> None:
        """Close database connection."""
        if self.blocking_db:
            self.blocking_db.close()
            self.blocking_db = None
