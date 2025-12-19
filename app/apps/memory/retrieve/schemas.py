"""Schemas for retrieve endpoints."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from ..models import Artifact, ArtifactChunk, Entity
from ..relation import Relation


class RetrieveResolution(StrEnum):
    """Resolution of the retrieval."""

    TYPE_ONLY = "type_only"
    MAJOR_TYPE_AND_NAME = "major_type_and_name"
    SELECTED_ENTITIES = "selected_entities"
    SELECTED_ENTITIES_AND_MUTUAL_RELATIONS = "selected_entities_and_mutual_relations"
    RELATED_ARTIFACTS_DATA = "related_artifacts_data"
    RELATED_ARTIFACTS_TEXT = "related_artifacts_text"


class RetrieveRequest(BaseModel):
    """Request model for retrieval."""

    tenant_id: str | None = Field(None, description="Tenant/organization ID")
    company_id: str | None = Field(None, description="Company ID")
    user_id: str | None = Field(None, description="User ID")
    group_id: str | None = Field(None, description="Group ID")

    resolution: RetrieveResolution | None = Field(
        None,
        description="Resolution of the retrieval",
    )
    entity_ids: list[str] | None = Field(
        None,
        description="""Entity IDs to retrieve""",
    )
    text: str | None = Field(None, description="Text for retrieval context")

    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validate tenant ID."""
        if v is None and info.data.get("company_id") is None:
            raise ValueError("Tenant ID is required")
        return v


class ArtifactWithChunks(BaseModel):
    """Artifact with its associated chunks."""

    artifact: Artifact = Field(..., description="Artifact data")
    chunks: list[ArtifactChunk] = Field(
        default_factory=list, description="Chunks belonging to this artifact"
    )


class RetrieveResponse(BaseModel):
    """Response model for retrieval."""

    tenant_id: str = Field(description="Tenant/organization ID")
    company_id: str = Field(description="Company ID")
    entities: list[Entity] = Field(..., description="Entities retrieved")
    relations: list[Relation] = Field(..., description="Relations retrieved")
    artifacts: list[ArtifactWithChunks] = Field(
        default_factory=list, description="Artifacts with their chunks"
    )

    context: str | None = Field(None, description="Context text retrieved")


class OldRetrieveRequest(BaseModel):
    """Request model for knowledge retrieval."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    question: str = Field(..., description="Natural language question")
    hints: dict[str, object] = Field(
        default_factory=dict,
        description="Optional hints (language, entity filters, time ranges, etc.)",
    )
    limits: dict[str, int] = Field(
        default_factory=lambda: {"max_entities": 20, "max_chunks": 20},
        description="Limits for results (max_entities, max_chunks)",
    )
    source_types: list[str] | None = Field(
        None, description="Optional filter by source types"
    )

    model_config = {"json_schema_extra": {"examples": []}}


class EntityResult(BaseModel):
    """Entity record returned in retrieve responses."""

    entity_id: str = Field("", description="Entity record ID")
    entity_type: str = Field("", description="Entity type")
    name: str = Field("", description="Entity name")
    attributes: dict[str, object] = Field(default_factory=dict)
    distance: float | None = Field(None, description="Optional graph distance score")


class RelationResult(BaseModel):
    """Relation record returned in retrieve responses."""

    relation_id: str = Field("", description="Relation record ID")
    from_entity_id: str = Field("", description="Source entity ID")
    to_entity_id: str = Field("", description="Target entity ID")
    relation_type: str = Field("", description="Relation type")
    attributes: dict[str, object] = Field(default_factory=dict)
    distance: float | None = Field(None, description="Optional graph distance score")


class ChunkResult(BaseModel):
    """Text chunk returned in RAG context."""

    chunk_id: str = Field("", description="Chunk record ID")
    source_id: str = Field("", description="Knowledge source ID")
    chunk_index: int = Field(0, description="Chunk index within source")
    score: float = Field(0.0, description="Similarity/relevance score")
    text: str = Field("", description="Chunk text content")


class RetrieveEntityResponse(BaseModel):
    """Response model for structured entity/relations retrieval."""

    tenant_id: str
    entities: list[EntityResult]
    relations: list[RelationResult]


class RagContext(BaseModel):
    """Context payload for RAG retrieval."""

    entities: list[EntityResult]
    relations: list[RelationResult]
    chunks: list[ChunkResult]


class RagRetrieveResponse(BaseModel):
    """Response model for RAG retrieval."""

    tenant_id: str
    question: str
    query_type: Literal["structured", "semantic", "hybrid"]
    filters: dict[str, object] | None = None
    context: RagContext
