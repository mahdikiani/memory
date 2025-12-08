"""Database models for ingestion domain."""

from datetime import datetime

from pydantic import Field

from db.models import BaseSurrealTenantEntity


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
