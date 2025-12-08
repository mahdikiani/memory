"""Functional helpers for managing entity relations."""

import logging
from datetime import datetime

from server.db import db_manager

from ..models import Relation

logger = logging.getLogger(__name__)


async def create_relation(
    tenant_id: str,
    from_entity_id: str,
    to_entity_id: str,
    relation_type: str,
    attributes: dict[str, object] | None = None,
    source_ids: list[str] | None = None,
) -> str:
    """Create a relation between entities."""
    db = db_manager.get_db()

    relation = Relation(
        tenant_id=tenant_id,
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        relation_type=relation_type,
        attributes=attributes or {},
        source_ids=source_ids or [],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    record_id = f"relation:{tenant_id}:{from_entity_id}:{relation_type}:{to_entity_id}"

    try:
        result = await db.create(record_id, relation.model_dump(exclude={"id"}))
        relation_id = (
            result.get("id", record_id) if isinstance(result, dict) else record_id
        )
        logger.info("Created relation: %s", relation_id)
    except Exception:
        logger.exception("Failed to create relation")
        raise

    return relation_id


async def get_relations(
    tenant_id: str,
    entity_id: str | None = None,
    relation_type: str | None = None,
    limit: int = 50,
) -> list[Relation]:
    """Get relations with optional filters."""
    db_manager.get_db()

    from db import execute_query, query

    query_builder = (
        query("relation")
        .where_eq("tenant_id", tenant_id)
        .where_eq("is_deleted", False)
        .limit(limit)
    )

    if entity_id:
        from_param = query_builder._add_param(entity_id)
        to_param = query_builder._add_param(entity_id)
        or_condition_parts = [
            "(",
            "from_entity_id",
            "=",
            from_param,
            "OR",
            "to_entity_id",
            "=",
            to_param,
            ")",
        ]
        query_builder._where_parts.append(" ".join(or_condition_parts))

    if relation_type:
        query_builder.where_eq("relation_type", relation_type)

    query_sql, query_params = query_builder.build()

    try:
        rows = await execute_query(query_sql, query_params)
        relations = [Relation(**row) for row in rows]
    except Exception:
        logger.exception("Failed to get relations")
        return []

    return relations
