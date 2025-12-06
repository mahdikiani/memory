"""Schemas for retrieve endpoints."""

from pydantic import BaseModel, Field


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
