"""Processor for structured content ingestion (direct entity/relation creation)."""

import logging

from server.db import db_manager

from ...utils.entity_service import EntityService
from ...utils.relation_service import RelationService
from ...utils.tenant_config_service import (
    get_tenant_entity_types_async,
    get_tenant_relation_types_async,
)

logger = logging.getLogger(__name__)

_entity_service = EntityService()
_relation_service = RelationService()


async def process_structured_entity(
    entity_data: dict[str, object],
    tenant_id: str,
    source_id: str,
) -> str:
    """
    Process and save a structured entity (user-confirmed).

    Args:
        entity_data: Entity data with entity_type, name, attributes
        tenant_id: Tenant ID
        source_id: Source record ID

    Returns:
        Entity record ID

    """
    # Validate against tenant config
    allowed_types = await get_tenant_entity_types_async(tenant_id)
    entity_type = str(entity_data.get("entity_type", ""))

    if allowed_types is not None and entity_type not in allowed_types:
        msg = (
            f"Entity type '{entity_type}' is not allowed for tenant '{tenant_id}'. "
            f"Allowed types: {allowed_types}"
        )
        raise ValueError(msg)

    # Create entity with user_confirmed confidence
    entity_id = await _entity_service.upsert_entity(
        tenant_id=tenant_id,
        entity_type=entity_type,
        name=str(entity_data.get("name", "")),
        attributes=dict(entity_data.get("attributes", {})),
        source_ids=[source_id],
    )

    # Set confidence level
    db = db_manager.get_db()
    await db.update(entity_id, {"confidence_level": "user_confirmed"})

    logger.info("Saved structured entity: %s", entity_id)
    return entity_id


async def process_structured_relation(
    relation_data: dict[str, object],
    tenant_id: str,
    source_id: str,
) -> str:
    """
    Process and save a structured relation (user-confirmed).

    Args:
        relation_data: Relation data with from_entity_id, to_entity_id,
                       relation_type, attributes
        tenant_id: Tenant ID
        source_id: Source record ID

    Returns:
        Relation record ID

    """
    # Validate against tenant config
    allowed_types = await get_tenant_relation_types_async(tenant_id)
    relation_type = str(relation_data.get("relation_type", ""))

    if allowed_types is not None and relation_type not in allowed_types:
        msg = (
            f"Relation type '{relation_type}' is not allowed for tenant '{tenant_id}'. "
            f"Allowed types: {allowed_types}"
        )
        raise ValueError(msg)

    # Create relation with user_confirmed confidence
    relation_id = await _relation_service.create_relation(
        tenant_id=tenant_id,
        from_entity_id=str(relation_data.get("from_entity_id", "")),
        to_entity_id=str(relation_data.get("to_entity_id", "")),
        relation_type=relation_type,
        attributes=dict(relation_data.get("attributes", {})),
        source_ids=[source_id],
    )

    # Set confidence level
    db = db_manager.get_db()
    await db.update(relation_id, {"confidence_level": "user_confirmed"})

    logger.info("Saved structured relation: %s", relation_id)
    return relation_id
