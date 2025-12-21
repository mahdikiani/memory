"""Database models for SurrealDB entities."""

from typing import ClassVar, Self

from aiocache import cached
from pydantic import ConfigDict, Field

from db.models import BaseSurrealEntity, RecordId

from .mixin import AuthorizationMixin, TenantSurrealMixin


class Company(BaseSurrealEntity):
    """Company model for storing company-specific settings."""

    _DEFAULT_ALLOWED_SENSOR_TYPES: ClassVar[list[str]] = [
        "initialization",
        "document",
        "meeting",
        # "calendar",
        # "task",
        # "crm",
        "chat",
    ]

    company_id: str = Field(
        ...,
        description="Company ID",
        json_schema_extra={"surreal_index": "idx_company_id"},
    )
    name: str = Field(
        ...,
        description="Company name",
        json_schema_extra={"surreal_index": "idx_company_name"},
    )
    sensor_types: list[str] = Field(
        default_factory=lambda: list(Company._DEFAULT_ALLOWED_SENSOR_TYPES),
        description="List of allowed sensor types for this company",
    )
    entity_types: list[str] | None = Field(
        None,
        description=(
            "List of allowed entity types for this company (None = all allowed)"
        ),
    )
    relation_types: list[str] | None = Field(
        None,
        description=(
            "List of allowed relation types for this company (None = all allowed)"
        ),
    )
    data: dict[str, object] = Field(
        default_factory=dict, description="Company additional data"
    )

    @cached(ttl=60 * 30)
    @classmethod
    async def get_by_id(
        cls,
        id: RecordId | str | None = None,  # noqa: A002
        company_id: str | None = None,
        is_deleted: bool = False,
    ) -> Self | None:
        """Get company by ID."""
        if id:
            return await super().get_by_id(id=RecordId(id), is_deleted=is_deleted)
        elif company_id:
            return await super().find_one(company_id=company_id, is_deleted=is_deleted)
        return None


class Entity(TenantSurrealMixin, AuthorizationMixin, BaseSurrealEntity):
    """Entity model for knowledge graph."""

    model_config = ConfigDict(json_schema_extra={"surreal_graph_node": True})

    name: str = Field(
        ...,
        description="Entity name",
        json_schema_extra={"surreal_index": "idx_entity_name"},
    )
    entity_type: str = Field(
        ...,
        description="Type of entity (person, company, etc.)",
        json_schema_extra={"surreal_index": "idx_entity_type"},
    )
    data: dict[str, object] = Field(default_factory=dict, description="Entity data")


class Artifact(TenantSurrealMixin, AuthorizationMixin, BaseSurrealEntity):
    """Artifact model for storing artifact data."""

    model_config = ConfigDict(json_schema_extra={"surreal_graph_node": True})

    uri: str | None = Field(None, description="URI of the artifact")
    sensor_name: str | None = Field(
        None, description="Name of the sensor/service that generated the artifact"
    )
    data: dict[str, object] = Field(default_factory=dict, description="Entity data")
    raw_text: str | None = Field(..., description="Raw text content of the artifact")

    async def get_text(self) -> str:
        """Get the text of the knowledge source from the chunks."""

        chunks = await ArtifactChunk.find_many(artifact_id=self.id, is_deleted=False)
        return "\n\n".join([chunk.text for chunk in chunks]) if chunks else ""


class ArtifactChunk(TenantSurrealMixin, AuthorizationMixin, BaseSurrealEntity):
    """Artifact chunk model for storing artifact chunk data."""

    artifact_id: RecordId = Field(
        description="Reference to artifact record",
        json_schema_extra={"surreal_index": "idx_tenant_artifact_id"},
    )
    chunk_index: int = Field(..., description="Index of chunk within source")
    text: str = Field(
        ...,
        description="Chunk text content",
        json_schema_extra={
            "surreal_index": "idx_tenant_chunk_text",
            "surreal_fulltext_field": True,
        },
    )
    embedding: list[float] | None = Field(
        None,
        description="Vector embedding",
        json_schema_extra={
            "surreal_index": "idx_tenant_chunk_embedding",
            "surreal_vector_field": True,
        },
    )


class Event(TenantSurrealMixin, AuthorizationMixin, BaseSurrealEntity):
    """Event model in the memory system."""

    entity_id: RecordId = Field(
        ...,
        description="Reference to entity record",
        json_schema_extra={"surreal_index": "idx_event_entity_id"},
    )
    artifact_ids: list[RecordId] = Field(
        default_factory=list,
        description="References to artifact records that related to the event",
        json_schema_extra={"surreal_index": "idx_event_artifact_id"},
    )

    event_type: str = Field(
        ...,
        description="Type of event",
        json_schema_extra={"surreal_index": "idx_tenant_event_type"},
    )
    data: dict[str, object] = Field(
        default_factory=dict, description="Entity event attributes"
    )
