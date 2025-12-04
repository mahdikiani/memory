"""Pydantic models for database entities matching SurrealDB schema definitions."""

from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from apps.base.schemas import SurrealTenantSchema


class TenantConfig(SurrealTenantSchema):
    """Tenant configuration model for storing tenant-specific settings."""

    source_types: list[str] = Field(
        default_factory=lambda: [
            "document",
            "meeting",
            "calendar",
            "task",
            "crm",
            "chat",
        ],
        description="List of allowed source types for this tenant",
    )
    entity_types: list[str] | None = Field(
        None, description="List of allowed entity types (None = all allowed)"
    )
    relation_types: list[str] | None = Field(
        None, description="List of allowed relation types (None = all allowed)"
    )


class KnowledgeSource(SurrealTenantSchema):
    """Knowledge source entity model."""

    source_type: str = Field(
        ...,
        description="Type of knowledge source",
        json_schema_extra={"surreal_index": "idx_tenant_source"},
    )
    source_id: str = Field(
        ...,
        description="External ID from the sensor/service",
        json_schema_extra={"surreal_index": "idx_tenant_source"},
    )
    sensor_name: str | None = Field(
        None,
        description="Name of the sensor/service",
        json_schema_extra={"surreal_index": "idx_tenant_sensor"},
    )

    @model_validator(mode="after")
    def validate_source_type(self) -> Self:
        """Validate source_type against tenant configuration."""
        from apps.knowledge.services.tenant_config_service import (
            get_tenant_source_types,
        )

        allowed_types = get_tenant_source_types(self.tenant_id)
        if self.source_type not in allowed_types:
            msg = (
                f"Source type '{self.source_type}' is not allowed for tenant "
                f"'{self.tenant_id}'. Allowed types: {allowed_types}"
            )
            raise ValueError(msg)
        return self


class KnowledgeChunk(SurrealTenantSchema):
    """Knowledge chunk entity model with vector embedding support."""

    source_id: str = Field(
        ...,
        description="Reference to knowledge_source record",
        json_schema_extra={"surreal_index": "idx_tenant_source"},
    )
    chunk_index: int = Field(..., description="Index of chunk within source")
    text: str = Field(..., description="Chunk text content")
    embedding: list[float] | None = Field(
        None,
        description="Vector embedding",
        json_schema_extra={"surreal_index": "idx_tenant_embedding"},
    )


class Entity(SurrealTenantSchema):
    """Entity model for knowledge graph."""

    entity_type: str = Field(
        ...,
        description="Type of entity (person, company, etc.)",
        json_schema_extra={"surreal_index": "idx_tenant_type"},
    )
    name: str = Field(
        ...,
        description="Entity name",
        json_schema_extra={"surreal_index": "idx_tenant_name"},
    )
    attributes: dict[str, object] = Field(
        default_factory=dict, description="Entity attributes"
    )
    source_ids: list[str] = Field(
        default_factory=list, description="References to knowledge_source records"
    )

    @model_validator(mode="after")
    def validate_entity_type(self) -> Self:
        """Validate entity_type against tenant configuration."""
        from apps.knowledge.services.tenant_config_service import (
            get_tenant_entity_types,
        )

        allowed_types = get_tenant_entity_types(self.tenant_id)
        if allowed_types is not None and self.entity_type not in allowed_types:
            msg = (
                f"Entity type '{self.entity_type}' is not allowed for tenant "
                f"'{self.tenant_id}'. Allowed types: {allowed_types}"
            )
            raise ValueError(msg)
        return self


class Relation(SurrealTenantSchema):
    """Relation model for knowledge graph edges."""

    from_entity_id: str = Field(
        ...,
        description="Reference to source entity record",
        json_schema_extra={"surreal_index": "idx_tenant_from"},
    )
    to_entity_id: str = Field(
        ...,
        description="Reference to target entity record",
        json_schema_extra={"surreal_index": "idx_tenant_to"},
    )
    relation_type: str = Field(
        ...,
        description="Type of relation",
        json_schema_extra={"surreal_index": "idx_tenant_type"},
    )
    attributes: dict[str, object] = Field(
        default_factory=dict, description="Relation attributes"
    )
    source_ids: list[str] = Field(
        default_factory=list, description="References to knowledge_source records"
    )

    @model_validator(mode="after")
    def validate_relation_type(self) -> Self:
        """Validate relation_type against tenant configuration."""
        from apps.knowledge.services.tenant_config_service import (
            get_tenant_relation_types,
        )

        allowed_types = get_tenant_relation_types(self.tenant_id)
        if allowed_types is not None and self.relation_type not in allowed_types:
            msg = (
                f"Relation type '{self.relation_type}' is not allowed for tenant "
                f"'{self.tenant_id}'. Allowed types: {allowed_types}"
            )
            raise ValueError(msg)
        return self


class IngestJob(SurrealTenantSchema):
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
