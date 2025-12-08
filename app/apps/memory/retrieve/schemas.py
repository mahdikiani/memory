"""Schemas for retrieve endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


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


class RetrieveRequest(BaseModel):
    """Request model for structured retrieval."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    entity_ids: list[str] | None = Field(
        None, description="Explicit entity IDs to fetch"
    )
    entity_type: str | None = Field(None, description="Filter by entity type")
    name: str | None = Field(None, description="Filter by entity name")
    relation_type: str | None = Field(None, description="Filter relations by type")
    related_entity_id: str | None = Field(
        None, description="Return relations touching this entity_id"
    )
    limit_entities: int = Field(20, ge=1, le=200)
    limit_relations: int = Field(50, ge=1, le=200)


class RagRetrieveRequest(OldRetrieveRequest):
    """Request model for RAG retrieval."""

    query_type: Literal["structured", "semantic", "hybrid"] | None = Field(
        None, description="Force query type; defaults to classifier"
    )


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
