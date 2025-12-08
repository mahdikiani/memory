"""Processor for handling relation extraction and storage."""

import logging

from server.db import db_manager

from ...utils.entity_service import find_entity
from ...utils.relation_service import create_relation
from ...utils.tenant_config_service import get_tenant_relation_types_async
from ..schemas import ExtractedRelation

logger = logging.getLogger(__name__)


async def filter_relations_by_tenant_config(
    relations: list[ExtractedRelation], tenant_id: str
) -> list[ExtractedRelation]:
    """
    Filter relations based on tenant configuration.

    Args:
        relations: List of extracted relations
        tenant_id: Tenant ID

    Returns:
        Filtered list of relations

    """
    allowed_types = await get_tenant_relation_types_async(tenant_id)

    # If None, all types are allowed
    if allowed_types is None:
        return relations

    # Filter by allowed types
    filtered = [
        relation for relation in relations if relation.relation_type in allowed_types
    ]

    if len(filtered) != len(relations):
        logger.info(
            "Filtered %d relations to %d based on tenant config (tenant: %s)",
            len(relations),
            len(filtered),
            tenant_id,
        )

    return filtered


async def resolve_entity_ids(
    relations: list[ExtractedRelation], tenant_id: str
) -> list[dict[str, str]]:
    """
    Resolve entity names to entity IDs.

    Args:
        relations: List of extracted relations with entity names
        tenant_id: Tenant ID

    Returns:
        List of relations with entity IDs resolved

    """
    resolved_relations: list[dict[str, str]] = []

    for relation in relations:
        try:
            from_entity = await find_entity(
                tenant_id, relation.from_entity_type, relation.from_entity_name
            )
            if not from_entity:
                logger.warning(
                    "Could not find entity: %s (%s)",
                    relation.from_entity_name,
                    relation.from_entity_type,
                )
                continue

            to_entity = await find_entity(
                tenant_id, relation.to_entity_type, relation.to_entity_name
            )
            if not to_entity:
                logger.warning(
                    "Could not find entity: %s (%s)",
                    relation.to_entity_name,
                    relation.to_entity_type,
                )
                continue

            resolved_relations.append({
                "from_entity_id": from_entity.id or "",
                "to_entity_id": to_entity.id or "",
                "relation_type": relation.relation_type,
                "attributes": relation.attributes,
                "confidence": relation.confidence,
            })

        except Exception:
            logger.exception(
                "Failed to resolve entity IDs for relation: %s -> %s",
                relation.from_entity_name,
                relation.to_entity_name,
            )
            continue

    return resolved_relations


async def save_relations(
    relations: list[ExtractedRelation],
    tenant_id: str,
    source_id: str,
) -> int:
    """
    Save relations to database.

    Args:
        relations: List of extracted relations
        tenant_id: Tenant ID
        source_id: Source record ID

    Returns:
        Number of relations saved

    """
    if not relations:
        return 0

    # Filter by tenant config
    filtered_relations = await filter_relations_by_tenant_config(relations, tenant_id)

    # Resolve entity names to IDs
    resolved = await resolve_entity_ids(filtered_relations, tenant_id)

    saved_count = 0

    for rel_data in resolved:
        try:
            relation_id = await create_relation(
                tenant_id=tenant_id,
                from_entity_id=rel_data["from_entity_id"],
                to_entity_id=rel_data["to_entity_id"],
                relation_type=rel_data["relation_type"],
                attributes=rel_data["attributes"],
                source_ids=[source_id],
            )

            # Update confidence_level
            db = db_manager.get_db()
            await db.update(relation_id, {"confidence_level": rel_data["confidence"]})

            saved_count += 1
            logger.debug("Saved relation: %s", relation_id)

        except Exception:
            logger.exception(
                "Failed to save relation: %s -> %s",
                rel_data["from_entity_id"],
                rel_data["to_entity_id"],
            )
            continue

    logger.info(
        "Saved %d relations for source %s (tenant: %s)",
        saved_count,
        source_id,
        tenant_id,
    )
    return saved_count
