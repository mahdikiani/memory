"""Schemas for FastAPI endpoints."""

from pydantic import BaseModel, Field, field_validator

from ..models import AuthorizationMixin, Entity
from ..relation import Relation


class BaseRelationIngestion(BaseModel):
    """Request model for structured relation ingestion."""

    relation_type: str = Field(..., description="Relation type")
    to_entity_id: str = Field(..., description="Target entity ID")
    data: dict[str, object] = Field(default_factory=dict)
    meta_data: dict[str, object] | None = Field(
        None, description="Additional metadata for the relation"
    )


class EntityIngestion(BaseModel):
    """Request model for structured entity ingestion."""

    id: str = Field(..., description="Internal ID for referencing in relations")
    entity_id: str | None = Field(
        None, description="Existing entity ID in database (for updates)"
    )
    entity_type: str = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    data: dict[str, object]
    meta_data: dict[str, object] | None = None


class RelationIngestion(BaseRelationIngestion):
    """Request model for structured relation ingestion."""

    from_entity_id: str = Field(..., description="Source entity ID")


class ContentIngestion(BaseModel):
    """Request model for content ingestion."""

    id: str | None = Field(None, description="Internal ID for referencing in relations")
    text: str = Field(..., description="Content to ingest")
    relations: list[BaseRelationIngestion] = Field(
        default_factory=list, description="Relations to ingest"
    )
    data: dict[str, object] = Field(default_factory=dict, description="Content data")
    meta_data: dict[str, object] | None = Field(
        None, description="Additional metadata for the content"
    )


class IngestRequest(AuthorizationMixin):
    """Request model for knowledge ingestion."""

    tenant_id: str | None = Field(None, description="Tenant/organization ID")
    company_id: str | None = Field(None, description="Company ID")

    sensor_name: str = Field(..., description="Name of the sensor")
    uri: str | None = Field(None, description="URI of the artifact")

    entities: list[EntityIngestion] = Field(
        default_factory=list,
        description="""Structured data to ingest""",
    )
    relations: list[RelationIngestion] = Field(
        default_factory=list,
        description="Relations to ingest",
    )
    contents: list[ContentIngestion] | str = Field(
        default_factory=list, description="Markdown text contents to ingest"
    )

    @field_validator("contents")
    @classmethod
    def validate_contents(cls, v: list[str] | str) -> list[str] | str:
        """Make the contents a list of strings."""

        if isinstance(v, str):
            return [v]
        return v


class IngestionResult(BaseModel):
    """Result of ingestion process."""

    job_ids: list[str] = Field(..., description="Ingestion job ID")
    entities: list[Entity] = Field(default_factory=list, description="Entities created")
    relations: list[Relation] = Field(
        default_factory=list, description="Relations created"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings during ingestion"
    )
