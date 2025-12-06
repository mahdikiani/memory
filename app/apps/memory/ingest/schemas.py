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
