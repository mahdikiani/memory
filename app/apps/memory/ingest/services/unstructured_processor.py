"""Processor for unstructured content ingestion."""

import logging

from server.config import Settings

from ...models import KnowledgeChunk
from ...utils.tenant_config_service import (
    get_tenant_entity_types_async,
    get_tenant_relation_types_async,
)
from ..chain import IngestionChain
from ..models import ExtractedEntity, ExtractedRelation
from ..text_processor import TextProcessor

logger = logging.getLogger(__name__)

_text_processor = TextProcessor()


async def process_unstructured(
    content: str,
    tenant_id: str,
    source_id: str,
    metadata: dict[str, object] | None = None,
    settings: Settings | None = None,
) -> tuple[list[KnowledgeChunk], list[ExtractedEntity], list[ExtractedRelation]]:
    """
    Process unstructured content: chunk text and extract entities/relations.

    Args:
        content: Text content to process
        tenant_id: Tenant ID
        source_id: Source record ID
        metadata: Additional metadata
        settings: Application settings

    Returns:
        Tuple of (chunks, entities, relations)

    """
    # Step 1: Chunk the text
    chunks = _text_processor.create_chunks(
        tenant_id=tenant_id,
        text=content,
        source_id=source_id,
        metadata=metadata,
    )

    # Step 2: Extract entities and relations using LLM
    # Get allowed types from tenant config for prompt context
    allowed_entity_types = await get_tenant_entity_types_async(tenant_id)
    allowed_relation_types = await get_tenant_relation_types_async(tenant_id)

    ingestion_chain = IngestionChain(settings)
    extraction_result = await ingestion_chain.process_text(
        content, tenant_id, allowed_entity_types, allowed_relation_types
    )

    # Step 3: Convert to ExtractedEntity and ExtractedRelation models
    entities: list[ExtractedEntity] = [
        ExtractedEntity(
            entity_type=str(e.get("entity_type", "")),
            name=str(e.get("name", "")),
            attributes=dict(e.get("attributes", {})),
            confidence="auto_extracted",
        )
        for e in extraction_result.get("entities", [])
        if e.get("entity_type") and e.get("name")
    ]

    relations: list[ExtractedRelation] = [
        ExtractedRelation(
            from_entity_name=str(r.get("from_entity_name", "")),
            from_entity_type=str(r.get("from_entity_type", "")),
            to_entity_name=str(r.get("to_entity_name", "")),
            to_entity_type=str(r.get("to_entity_type", "")),
            relation_type=str(r.get("relation_type", "")),
            attributes=dict(r.get("attributes", {})),
            confidence="auto_extracted",
        )
        for r in extraction_result.get("relations", [])
        if r.get("from_entity_name")
        and r.get("to_entity_name")
        and r.get("relation_type")
    ]

    logger.info(
        "Processed unstructured content: %d chunks, %d entities, %d relations",
        len(chunks),
        len(entities),
        len(relations),
    )

    return chunks, entities, relations
