"""Routes for ingest endpoints."""

from fastapi import APIRouter

from .schemas import (
    IngestRequest,
    StructuredEntityIngestRequest,
    StructuredRelationIngestRequest,
)
from .services.ingestion_service import IngestionService

ingestion_service = IngestionService()

router = APIRouter(tags=["ingest"])


@router.post("/ingest/entity")
async def ingest_entity(payload: StructuredEntityIngestRequest) -> dict[str, object]:
    """Ingest a user-confirmed entity without LLM processing."""
    entity_id = await ingestion_service.ingest_structured_entity(
        entity_data={
            "entity_type": payload.entity_type,
            "name": payload.name,
            "attributes": payload.attributes,
        },
        tenant_id=payload.tenant_id,
        source_id=payload.source_id,
        source_type=payload.source_type,
        sensor_name=payload.sensor_name,
    )
    return {
        "tenant_id": payload.tenant_id,
        "entity_id": entity_id,
    }


@router.post("/ingest/relation")
async def ingest_relation(
    payload: StructuredRelationIngestRequest,
) -> dict[str, object]:
    """Ingest a user-confirmed relation without LLM processing."""
    relation_id = await ingestion_service.ingest_structured_relation(
        relation_data={
            "from_entity_id": payload.from_entity_id,
            "to_entity_id": payload.to_entity_id,
            "relation_type": payload.relation_type,
            "attributes": payload.attributes,
        },
        tenant_id=payload.tenant_id,
        source_id=payload.source_id,
        source_type=payload.source_type,
        sensor_name=payload.sensor_name,
    )
    return {
        "tenant_id": payload.tenant_id,
        "relation_id": relation_id,
    }


@router.post("/ingest")
async def ingest_unstructured(payload: IngestRequest) -> dict[str, object]:
    """Ingest unstructured text content using the LLM pipeline."""
    result = await ingestion_service.ingest_unstructured(
        content=payload.content,
        source_type=payload.source_type,
        source_id=payload.source_id,
        tenant_id=payload.tenant_id,
        metadata=payload.metadata,
        sensor_name=payload.sensor_name,
    )
    return result.model_dump()
