"""Pydantic models for database entities matching SurrealDB schema definitions."""

from datetime import datetime

from pydantic import BaseModel, Field


class BaseSurrealTenantEntity(BaseModel):
    """SurrealDB tenant schema base model."""

    id: str | None = Field(
        None,
        description="Record ID",
        json_schema_extra={"surreal_index": "idx_id"},
    )
    tenant_id: str = Field(
        ...,
        description="Tenant/organization ID",
        json_schema_extra={"surreal_index": "idx_tenant_id"},
    )
    created_at: datetime | None = Field(
        None,
        description="Creation timestamp",
    )
    updated_at: datetime | None = Field(
        None,
        description="Last update timestamp",
    )
    is_deleted: bool = Field(
        False,
        description="Whether the record is deleted",
    )
    meta_data: dict[str, object] | None = Field(
        default_factory=None, description="Additional metadata"
    )
