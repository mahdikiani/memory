"""Schemas for FastAPI endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request model for knowledge ingestion."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    source_type: Literal["document", "meeting", "calendar", "task", "crm", "chat"] = (
        Field(..., description="Type of knowledge source")
    )
    source_id: str = Field(..., description="External ID from the sensor/service")
    sensor_name: str | None = Field(
        None, description="Name of the sensor/service that created this data"
    )
    content: str = Field(..., description="Markdown text content to ingest")
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="Additional metadata (title, datetime, participants, tags, etc.)",
    )

    model_config = {"json_schema_extra": {"examples": []}}


class StructuredEntityIngestRequest(BaseModel):
    """Request model for structured entity ingestion."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    entity_type: str = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    attributes: dict[str, object] = Field(default_factory=dict)
    source_type: str = Field(..., description="Source type for provenance")
    source_id: str = Field(..., description="External source identifier")
    sensor_name: str | None = Field(None, description="Optional sensor/service name")


class StructuredRelationIngestRequest(BaseModel):
    """Request model for structured relation ingestion."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    from_entity_id: str = Field(..., description="Source entity ID")
    to_entity_id: str = Field(..., description="Target entity ID")
    relation_type: str = Field(..., description="Relation type")
    attributes: dict[str, object] = Field(default_factory=dict)
    source_type: str = Field(..., description="Source type for provenance")
    source_id: str = Field(..., description="External source identifier")
    sensor_name: str | None = Field(None, description="Optional sensor/service name")


class ExtractedEntity(BaseModel):
    """Entity extracted from unstructured text."""

    entity_type: str = Field(..., description="Type of entity")
    name: str = Field(..., description="Entity name")
    attributes: dict[str, object] = Field(
        default_factory=dict, description="Entity attributes"
    )
    confidence: Literal["user_confirmed", "auto_extracted"] = Field(
        default="auto_extracted", description="Confidence level"
    )


class ExtractedRelation(BaseModel):
    """Relation extracted from unstructured text."""

    from_entity_name: str = Field(..., description="Source entity name")
    from_entity_type: str = Field(..., description="Source entity type")
    to_entity_name: str = Field(..., description="Target entity name")
    to_entity_type: str = Field(..., description="Target entity type")
    relation_type: str = Field(..., description="Type of relation")
    attributes: dict[str, object] = Field(
        default_factory=dict, description="Relation attributes"
    )
    confidence: Literal["user_confirmed", "auto_extracted"] = Field(
        default="auto_extracted", description="Confidence level"
    )


class IngestionResult(BaseModel):
    """Result of ingestion process."""

    job_id: str = Field(..., description="Ingestion job ID")
    chunks_count: int = Field(default=0, description="Number of chunks created")
    entities_count: int = Field(default=0, description="Number of entities extracted")
    relations_count: int = Field(default=0, description="Number of relations extracted")
