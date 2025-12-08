"""API routes for memory service."""

from fastapi import APIRouter, HTTPException

from .ingest.routes import router as ingest_router
from .retrieve.routes import router as retrieve_router
from .utils.tenant_config_service import get_tenant_config_async

router = APIRouter()


@router.get("/metadata", tags=["memory"])
async def get_metadata(tenant_id: str) -> dict[str, object]:
    """Get tenant configuration."""

    config = await get_tenant_config_async(tenant_id)
    if not config:
        raise HTTPException(status_code=404, detail="Tenant config not found")

    return {
        "tenant_id": tenant_id,
        "source_types": config.source_types,
        "entity_types": config.entity_types,
        "relation_types": config.relation_types,
    }


router.include_router(ingest_router)
router.include_router(retrieve_router)
