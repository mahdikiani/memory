"""Database models for ingestion domain."""

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from db.models import BaseSurrealEntity

from ..models import TenantSurrealMixin


class IngestStatus(StrEnum):
    """Ingest job status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_queued(self) -> bool:
        """Check if the job is queued."""
        return self in {IngestStatus.QUEUED}


class IngestJob(TenantSurrealMixin, BaseSurrealEntity):
    """Ingest job entity model."""

    status: IngestStatus = Field(
        IngestStatus.QUEUED,
        description="Ingest job status",
        json_schema_extra={"surreal_index": "idx_tenant_status"},
    )
    artifact_id: str = Field(
        ...,
        description="Reference to knowledge_source record",
        json_schema_extra={"surreal_index": "idx_tenant_source"},
    )
    error_message: str | None = Field(None, description="Error message if failed")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
