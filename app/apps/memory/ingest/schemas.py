"""Schemas for FastAPI endpoints."""

from pydantic import BaseModel, Field, field_validator

from ..models import Entity


class BaseRelationIngestion(BaseModel):
    """Request model for structured relation ingestion."""

    relation_type: str = Field(..., description="Relation type")
    to_entity_id: str = Field(..., description="Target entity ID")
    data: dict[str, object] = Field(default_factory=dict)


class EntityIngestion(BaseModel):
    """Request model for structured entity ingestion."""

    entity_id: str | None = Field(None, description="Entity ID")
    entity_type: str = Field(..., description="Entity type")
    name: str = Field(..., description="Entity name")
    data: dict[str, object]
    meta_data: dict[str, object] | None = None

    relations: list[BaseRelationIngestion] = Field(
        default_factory=list, description="Relations to ingest"
    )


class RelationIngestion(BaseRelationIngestion):
    """Request model for structured relation ingestion."""

    from_entity_id: str = Field(..., description="Source entity ID")


class IngestRequest(BaseModel):
    """Request model for knowledge ingestion."""

    tenant_id: str = Field(..., description="Tenant/organization ID")

    sensor_name: str = Field(..., description="Name of the sensor")
    uri: str | None = Field(None, description="URI of the artifact")

    entities: list[EntityIngestion] = Field(
        default_factory=dict,
        description="""Structured data to ingest""",
    )
    relations: list[RelationIngestion] = Field(
        default_factory=list,
        description="Relations to ingest",
    )
    contents: list[str] | str = Field(
        default_factory=list, description="Markdown text contents to ingest"
    )

    meta_data: dict[str, object] | None = Field(
        None,
        description="Additional metadata for the ingestion attached to all contents",
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
    relations: list[RelationIngestion] = Field(
        default_factory=list, description="Relations created"
    )
