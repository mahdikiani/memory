"""Processor for handling entity extraction and storage."""

import logging

from server.db import db_manager

from ...utils.entity_service import EntityService
from ...utils.tenant_config_service import get_tenant_entity_types_async
from ..models import ExtractedEntity

logger = logging.getLogger(__name__)

_entity_service = EntityService()


async def filter_entities_by_tenant_config(
    entities: list[ExtractedEntity], tenant_id: str
) -> list[ExtractedEntity]:
    """
    Filter entities based on tenant configuration.

    Args:
        entities: List of extracted entities
        tenant_id: Tenant ID

    Returns:
        Filtered list of entities

    """
    allowed_types = await get_tenant_entity_types_async(tenant_id)

    # If None, all types are allowed
    if allowed_types is None:
        return entities

    # Filter by allowed types
    filtered = [entity for entity in entities if entity.entity_type in allowed_types]

    if len(filtered) != len(entities):
        logger.info(
            "Filtered %d entities to %d based on tenant config (tenant: %s)",
            len(entities),
            len(filtered),
            tenant_id,
        )

    return filtered


async def save_entities(
    entities: list[ExtractedEntity],
    tenant_id: str,
    source_id: str,
) -> int:
    """
    Save entities to database.

    Args:
        entities: List of extracted entities
        tenant_id: Tenant ID
        source_id: Source record ID

    Returns:
        Number of entities saved

    """
    if not entities:
        return 0

    # Filter by tenant config
    filtered_entities = await filter_entities_by_tenant_config(entities, tenant_id)

    saved_count = 0

    for extracted_entity in filtered_entities:
        try:
            # Convert ExtractedEntity to Entity and save
            entity_id = await _entity_service.upsert_entity(
                tenant_id=tenant_id,
                entity_type=extracted_entity.entity_type,
                name=extracted_entity.name,
                attributes=extracted_entity.attributes,
                source_ids=[source_id],
            )

            # Update confidence_level if needed
            # Note: upsert_entity doesn't support confidence_level yet
            # We'll need to update the entity after creation
            db = db_manager.get_db()
            await db.update(
                entity_id, {"confidence_level": extracted_entity.confidence}
            )

            saved_count += 1
            logger.debug("Saved entity: %s", entity_id)

        except Exception:
            logger.exception(
                "Failed to save entity: %s (%s)",
                extracted_entity.name,
                extracted_entity.entity_type,
            )
            continue

    logger.info(
        "Saved %d entities for source %s (tenant: %s)",
        saved_count,
        source_id,
        tenant_id,
    )
    return saved_count
