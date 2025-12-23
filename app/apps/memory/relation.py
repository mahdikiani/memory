"""Relation model for storing relation data."""

import logging
import re
from datetime import datetime, timezone
from typing import Self

from pydantic import ConfigDict, Field

from db.manager import AsyncSurrealConnection, DatabaseManager
from db.models import BaseSurrealEntity, RecordId
from db.query_executor import execute_query

from .mixin import AuthorizationMixin, TenantSurrealMixin

logger = logging.getLogger(__name__)


class Relation(TenantSurrealMixin, AuthorizationMixin, BaseSurrealEntity):
    """Relation model for storing relation data."""

    model_config = ConfigDict(json_schema_extra={"surreal_graph_edge": True})

    source_id: RecordId = Field(..., description="Source ID")
    target_id: RecordId = Field(..., description="Target ID")
    relation_type: str = Field(..., description="Relation type")
    data: dict[str, object] = Field(default_factory=dict, description="Relation data")

    @staticmethod
    def _validate_table_name(table_name: str) -> None:
        """
        Validate table name to prevent SQL injection.

        Args:
            table_name: Table name to validate

        Raises:
            ValueError if table name is invalid
        """
        # Validate table name format (alphanumeric, hyphen, underscore)
        if not re.match(r"^[a-zA-Z0-9_-]+$", table_name):
            raise ValueError(f"Invalid table name format: {table_name}")

    @classmethod
    def _get_table_name(cls, relation_type: str | None = None) -> str:
        """
        Get table name from relation_type.

        In SurrealDB, when using RELATE source -> relation_type -> target,
        the edge is stored in a table with the name of relation_type.
        """
        if relation_type:
            cls._validate_table_name(relation_type)
            return relation_type
        # If called as instance method, use self.relation_type
        # This is a fallback for class-level calls
        return "relation"

    async def save(self) -> Self:
        """
        Save (create or update) this instance using RELATE command.

        - Uses RELATE command to create/update edge in SurrealDB
        - If id exists: updates the edge
        - If id is None: creates new edge with RELATE
        - Auto-sets timestamps if enabled

        Returns:
            Self (for method chaining)

        Raises:
            Exception if Settings.raise_on_error is True
        """
        db_manager = DatabaseManager()
        db = db_manager.get_db()
        now = datetime.now(timezone.utc)  # noqa: UP017

        # Set timestamps if enabled and needed
        if not self.id and not self.created_at:
            self.created_at = now
        self.updated_at = now

        # Prepare data for RELATE command
        # Exclude id, source_id, target_id, relation_type from SET
        # as they are part of RELATE syntax
        data = self.model_dump(
            exclude={"id", "source_id", "target_id", "relation_type"},
            exclude_none=True,
        )

        try:
            if self.id:
                # Update existing relation
                await self._update_existing(db, data, now)
            else:
                # Create new relation using RELATE
                await self._create_with_relate(db, data, now)

            logger.debug(
                "Saved relation: %s -> %s -> %s",
                self.source_id,
                self.relation_type,
                self.target_id,
            )
        except Exception:
            logger.exception(
                "Failed to save relation: %s -> %s -> %s",
                self.source_id,
                self.relation_type,
                self.target_id,
            )
            if self.Settings.raise_on_error:
                raise

        return self

    async def _create_with_relate(
        self, db: AsyncSurrealConnection, data: dict[str, object], now: datetime
    ) -> Self:
        """Create relation using RELATE command."""
        # Build RELATE command
        # RELATE source -> relation_type -> target SET fields
        # Validate relation_type to prevent SQL injection
        self._validate_table_name(self.relation_type)
        relate_query = (
            f"RELATE {self.source_id} -> relation -> {self.target_id} "
            f"SET tenant_id = $tenant_id, "
            f"relation_type = $relation_type, "
            f"updated_at = $updated_at, "
            f"is_deleted = false, "
            f"created_at = $created_at"
        )

        # Add other fields from data
        for key in data:
            if key not in ("tenant_id", "relation_type", "updated_at", "created_at"):
                relate_query += f", {key} = ${key}"

        variables = {
            "tenant_id": self.tenant_id,
            "relation_type": self.relation_type,
            "updated_at": now,
            "created_at": now,
            **data,
        }

        # Execute RELATE command
        await db.query(relate_query, variables)

        # Find the created relation to get its ID
        # Validate table name to prevent SQL injection
        table_name = self.relation_type
        self._validate_table_name(table_name)
        # Table name is validated above, safe to use in query
        find_query = (
            f"SELECT * FROM {table_name} "  # noqa: S608
            "WHERE out = $source_id "
            "AND `in` = $target_id "
            "AND relation_type = $relation_type "
            "AND tenant_id = $tenant_id "
            "AND is_deleted = false "
            "LIMIT 1"
        )

        find_variables = {
            "source_id": str(self.source_id),
            "target_id": str(self.target_id),
            "relation_type": self.relation_type,
            "tenant_id": self.tenant_id,
        }

        results = await execute_query(find_query, find_variables)

        if not results:
            raise ValueError(
                f"Failed to find relation after RELATE: "
                f"{self.source_id} -> {self.relation_type} -> {self.target_id}"
            )

        # Set the ID from the created record
        if "id" in results[0]:
            self.id = RecordId(results[0]["id"])

        return self

    async def _update_existing(
        self, db: AsyncSurrealConnection, data: dict[str, object], now: datetime
    ) -> None:
        """Update existing relation."""
        if not self.id:
            raise ValueError("Cannot update relation without ID")

        # Update the edge record
        update_data = {**data, "updated_at": now}
        await db.update(self.id, update_data)

    async def update(self, **updates: object) -> dict[str, object]:
        """
        Update specific fields of this instance.

        Args:
            **updates: Fields to update

        Raises:
            ValueError if id is not set
            Exception if Settings.raise_on_error is True

        Returns:
            dict[str, object] - The old data that has changed
        """
        if not self.id:
            raise ValueError("Model must have id set to update")

        db_manager = DatabaseManager()
        db = db_manager.get_db()
        now = datetime.now(timezone.utc)  # noqa: UP017

        # Only update provided fields
        update_data = {**updates, "updated_at": now}
        old_data = {}
        try:
            await db.update(self.id, update_data)
            logger.debug("Updated relation: %s", self.id)

            # Update local instance
            for key, value in updates.items():
                if getattr(self, key, None) != value:
                    old_data[key] = getattr(self, key)
                    setattr(self, key, value)

            old_data["updated_at"] = now
            self.updated_at = now

        except Exception:
            logger.exception("Failed to update relation: %s", self.id)
            if self.Settings.raise_on_error:
                raise

        return old_data

    async def delete(self, soft: bool = True) -> None:
        """
        Delete this instance (soft or hard delete).

        Args:
            soft: If True, sets is_deleted=True (soft delete)
                  If False, permanently deletes the record

        Raises:
            ValueError if id is not set
            Exception if Settings.raise_on_error is True
        """
        if not self.id:
            raise ValueError("Model must have id set to delete")

        db_manager = DatabaseManager()
        db = db_manager.get_db()

        try:
            if soft:
                # Soft delete
                await self.update(is_deleted=True)
                self.is_deleted = True
            else:
                # Hard delete
                await db.delete(self.id)
                logger.debug("Deleted relation: %s", self.id)

        except Exception:
            logger.exception("Failed to delete relation: %s", self.id)
            if self.Settings.raise_on_error:
                raise

    @classmethod
    async def get_by_id(
        cls,
        id: str,  # noqa: A002
        is_deleted: bool = False,
    ) -> Self | None:
        """Get an instance by id."""
        return await cls.find_one(id=id, is_deleted=is_deleted)

    @classmethod
    async def find_one(
        cls, relation_type: str, is_deleted: bool = False, **filters: object
    ) -> Self | None:
        """
        Find one relation by filters.

        Args:
            relation_type: Type of relation (required to know which table to query)
            is_deleted: Filter by is_deleted status (default: False)
            **filters: Additional filter conditions

        Returns:
            Model instance or None if not found
        """
        table = cls._get_table_name(relation_type)
        # Validate table name to prevent SQL injection
        cls._validate_table_name(table)

        # Build query with 'out' and 'in' fields for edge queries
        # Table name is validated above, safe to use in query
        query_parts = [f"SELECT * FROM {table}"]  # noqa: S608
        where_parts = ["is_deleted = $is_deleted"]
        variables = {"is_deleted": is_deleted}

        # Handle source_id and target_id filters (map to 'out' and 'in')
        if "source_id" in filters:
            where_parts.append("out = $source_id")
            variables["source_id"] = str(filters.pop("source_id"))
        if "target_id" in filters:
            where_parts.append("`in` = $target_id")
            variables["target_id"] = str(filters.pop("target_id"))

        # Add other filters
        for param_counter, (field, value) in enumerate(filters.items()):
            param_name = f"param_{param_counter}"
            where_parts.append(f"{field} = ${param_name}")
            variables[param_name] = value

        if where_parts:
            query_parts.append("WHERE " + " AND ".join(where_parts))

        query_parts.append("LIMIT 1")

        query_sql = " ".join(query_parts)

        try:
            rows = await execute_query(query_sql, variables)
            if rows:
                # Map 'out' to source_id and 'in' to target_id
                relation_data = rows[0].copy()
                if "out" in relation_data:
                    relation_data["source_id"] = relation_data.pop("out")
                if "in" in relation_data:
                    relation_data["target_id"] = relation_data.pop("in")
                return cls(**relation_data)
        except Exception:
            logger.exception("Failed to find relation in table: %s", table)

        return None

    @classmethod
    def _build_find_query(
        cls,
        table: str,
        is_deleted: bool,
        skip: int,
        limit: int,
        filters: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        """
        Build query for finding relations.

        Args:
            table: Table name
            is_deleted: Filter by is_deleted status
            skip: Number of results to skip
            limit: Maximum number of results
            filters: Filter conditions

        Returns:
            Tuple of (query_sql, variables)
        """
        query_parts = [f"SELECT * FROM {table}"]  # noqa: S608
        where_parts = ["is_deleted = $is_deleted"]
        variables = {"is_deleted": is_deleted}

        # Handle source_id and target_id filters (map to 'out' and 'in')
        if "source_id" in filters:
            where_parts.append("out = $source_id")
            variables["source_id"] = str(filters.pop("source_id"))
        if "target_id" in filters:
            where_parts.append("`in` = $target_id")
            variables["target_id"] = str(filters.pop("target_id"))

        # Add other filters
        for param_counter, (field, value) in enumerate(filters.items()):
            param_name = f"param_{param_counter}"
            if isinstance(value, list):
                where_parts.append(f"{field} IN ${param_name}")
            else:
                where_parts.append(f"{field} = ${param_name}")
            variables[param_name] = value

        if where_parts:
            query_parts.append("WHERE " + " AND ".join(where_parts))

        if skip > 0:
            query_parts.append(f"SKIP {skip}")
        if limit > 0:
            query_parts.append(f"LIMIT {limit}")

        return " ".join(query_parts), variables

    @classmethod
    def _map_row_to_relation(cls, row: dict[str, object]) -> Self:
        """
        Map database row to Relation instance.

        Args:
            row: Database row with 'out' and 'in' fields

        Returns:
            Relation instance
        """
        relation_data = row.copy()
        if "out" in relation_data:
            relation_data["source_id"] = relation_data.pop("out")
        if "in" in relation_data:
            relation_data["target_id"] = relation_data.pop("in")
        return cls(**relation_data)

    @classmethod
    async def find_many(
        cls,
        relation_type: str,
        skip: int = 0,
        limit: int = 100,
        is_deleted: bool = False,
        **filters: object,
    ) -> list[Self]:
        """
        Find many relations by filters.

        Args:
            relation_type: Type of relation (required to know which table to query)
            skip: Number of results to skip
            limit: Maximum number of results
            is_deleted: Filter by is_deleted status (default: False)
            **filters: Additional filter conditions

        Returns:
            List of model instances
        """
        table = cls._get_table_name(relation_type)
        cls._validate_table_name(table)

        query_sql, variables = cls._build_find_query(
            table, is_deleted, skip, limit, filters
        )

        try:
            rows = await execute_query(query_sql, variables)
            return [cls._map_row_to_relation(row) for row in rows]
        except Exception:
            logger.exception("Failed to find many relations in table: %s", table)
            return []
