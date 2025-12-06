"""Entity service for managing entities."""

import logging
from datetime import datetime
from typing import Any

from apps.knowledge.schemas import Entity
from server.db import db_manager

logger = logging.getLogger(__name__)


class EntityService:
    """Service for managing entities."""

    async def upsert_entity(
        self,
        tenant_id: str,
        entity_type: str,
        name: str,
        attributes: dict[str, Any] | None = None,
        source_ids: list[str] | None = None,
    ) -> str:
        """
        Create or update an entity.

        Args:
            tenant_id: Tenant ID
            entity_type: Type of entity
            name: Entity name
            attributes: Entity attributes
            source_ids: List of source IDs this entity is linked to

        Returns:
            Entity record ID

        """
        db = db_manager.get_db()

        # Try to find existing entity by tenant_id, entity_type, and name
        existing = await self._find_entity(tenant_id, entity_type, name)

        if existing:
            # Update existing entity
            update_data: dict[str, Any] = {
                "updated_at": datetime.now(),
            }
            if attributes is not None:
                update_data["attributes"] = attributes
            if source_ids is not None:
                # Merge source IDs
                existing_sources = set(existing.source_ids)
                existing_sources.update(source_ids)
                update_data["source_ids"] = list(existing_sources)

            await db.update(existing.id, update_data)
            logger.debug("Updated entity: %s", existing.id)
            return existing.id
        else:
            # Create new entity
            entity = Entity(
                tenant_id=tenant_id,
                entity_type=entity_type,
                name=name,
                attributes=attributes or {},
                source_ids=source_ids or [],
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            # Generate record ID
            record_id = (
                f"entity:{tenant_id}:{entity_type}:{name.lower().replace(' ', '_')}"
            )

            try:
                result = await db.create(record_id, entity.model_dump(exclude={"id"}))
                entity_id = (
                    result.get("id", record_id)
                    if isinstance(result, dict)
                    else record_id
                )
                logger.info("Created entity: %s", entity_id)
            except Exception:
                logger.exception("Failed to create entity")
                raise

            return entity_id

    async def _find_entity(
        self, tenant_id: str, entity_type: str, name: str
    ) -> Entity | None:
        """Find entity by tenant_id, entity_type, and name."""
        from apps.knowledge.utils.query_builder_orm import query
        from apps.knowledge.utils.query_executor import execute_query

        # Build safe query using ORM-like builder (no string interpolation!)
        query_builder = (
            query("entity")
            .where_eq("tenant_id", tenant_id)
            .where_eq("entity_type", entity_type)
            .where_eq("name", name)
            .where_eq("is_deleted", False)
            .limit(1)
        )

        query_sql, params = query_builder.build()

        try:
            rows = await execute_query(query_sql, params)
            if rows:
                return Entity(**rows[0])
        except Exception:
            logger.exception("Failed to find entity")
            return None

        return None

    async def get_entities(
        self,
        tenant_id: str,
        filters: dict[str, Any] | None = None,
        limit: int = 20,
    ) -> list[Entity]:
        """
        Get entities with optional filters.

        Args:
            tenant_id: Tenant ID
            filters: Optional filters (entity_type, name, etc.)
            limit: Maximum number of results

        Returns:
            List of entities

        """
        # Build safe query using ORM-like builder (no string interpolation!)
        from apps.knowledge.utils.query_builder_orm import query
        from apps.knowledge.utils.query_executor import execute_query

        query_builder = (
            query("entity")
            .where_eq("tenant_id", tenant_id)
            .where_eq("is_deleted", False)
            .limit(limit)
        )

        if filters:
            for field, value in filters.items():
                if isinstance(value, list):
                    query_builder.where_in(field, value)
                else:
                    query_builder.where_eq(field, value)

        query_sql, query_params = query_builder.build()

        try:
            rows = await execute_query(query_sql, query_params)
            entities = [Entity(**row) for row in rows]
        except Exception:
            logger.exception("Failed to get entities")
            return []

        return entities

    async def link_entity_to_source(self, entity_id: str, source_id: str) -> None:
        """
        Link an entity to a knowledge source.

        Args:
            entity_id: Entity ID
            source_id: Knowledge source ID

        """
        db = db_manager.get_db()

        try:
            entity = await db.select(entity_id)
            if entity:
                source_ids = entity.get("source_ids", [])
                if source_id not in source_ids:
                    source_ids.append(source_id)
                    await db.update(entity_id, {"source_ids": source_ids})
                    logger.debug("Linked entity %s to source %s", entity_id, source_id)
        except Exception:
            logger.exception("Failed to link entity to source")
            raise
