"""Ingestion models for processing and extracting entities/relations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ...base.models import BaseSurrealTenantEntity


class IngestJob(BaseSurrealTenantEntity):
    """Ingest job entity model."""

    status: str = Field(
        ...,
        description="Job status",
        json_schema_extra={"surreal_index": "idx_tenant_status"},
    )
    source_type: str = Field(..., description="Type of knowledge source")
    source_id: str = Field(
        ...,
        description="External ID from the sensor/service",
        json_schema_extra={"surreal_index": "idx_tenant_source"},
    )
    error_message: str | None = Field(None, description="Error message if failed")
    completed_at: datetime | None = Field(None, description="Completion timestamp")


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
