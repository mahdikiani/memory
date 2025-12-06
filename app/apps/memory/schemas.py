"""Response schemas for FastAPI endpoints."""

from pydantic import BaseModel, Field


class EntityResponse(BaseModel):
    """Entity in retrieval response."""

    type: str = Field(..., description="Entity type (person, company, project, etc.)")
    id: str = Field(..., description="Entity ID")
    data: dict[str, object] = Field(..., description="Entity data/attributes")


class ChunkResponse(BaseModel):
    """Text chunk in retrieval response."""

    id: str = Field(..., description="Chunk ID")
    document_id: str = Field(..., description="Source document ID")
    source_type: str = Field(..., description="Source type")
    score: float = Field(..., description="Relevance score")
    text: str = Field(..., description="Chunk text content")
    metadata: dict[str, object] = Field(
        default_factory=dict, description="Additional chunk metadata"
    )


class ContextResponse(BaseModel):
    """Context returned in retrieval response."""

    entities: list[EntityResponse] = Field(
        default_factory=list, description="Relevant entities"
    )
    chunks: list[ChunkResponse] = Field(
        default_factory=list, description="Relevant text chunks"
    )


class IngestResponse(BaseModel):
    """Response model for knowledge ingestion."""

    job_id: str = Field(..., description="Ingestion job ID")
    status: str = Field(..., description="Job status (queued, processing, etc.)")


class RetrieveResponse(BaseModel):
    """Response model for knowledge retrieval."""

    tenant_id: str = Field(..., description="Tenant/organization ID")
    question: str = Field(..., description="Original question")
    context: ContextResponse = Field(..., description="Retrieved context")


class JobStatusResponse(BaseModel):
    """Response model for job status query."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    progress: float | None = Field(None, description="Job progress (0.0-1.0)")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: str = Field(..., description="Job creation timestamp")
    updated_at: str = Field(..., description="Job last update timestamp")
    completed_at: str | None = Field(None, description="Job completion timestamp")
