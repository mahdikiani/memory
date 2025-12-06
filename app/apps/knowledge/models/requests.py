"""Request models for knowledge API endpoints."""

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


class RetrieveRequest(BaseModel):
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
