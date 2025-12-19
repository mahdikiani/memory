"""API routes for memory service."""


from fastapi import APIRouter

from .exceptions import BaseHTTPException
from .ingest.routes import ingest
from .ingest.routes import router as ingest_router
from .models import Company
from .retrieve.routes import router as retrieve_router
from .schemas import CreateCompanySchema
from .services import create_company

router = APIRouter()


@router.get("/company", tags=["company"])
async def get_companies() -> list[Company]:
    """Get all companies."""

    companies = await Company.find_many(is_deleted=False)
    return companies


@router.post("/company", tags=["company"])
async def initialize_company(payload: CreateCompanySchema) -> Company:
    """Create a company entity and ingest its introductory content."""

    company = await create_company(payload)

    await ingest(payload)

    return company


@router.get("/company/{company_id}/metadata", tags=["company"])
async def get_company_metadata(company_id: str) -> Company:
    """Get company metadata."""

    company = await Company.find_one(company_id=company_id)
    if not company:
        raise BaseHTTPException(
            status_code=404, error="company_not_found", detail="Company not found"
        )

    return company


@router.get("/company/{company_id}/abstract", tags=["memory"])
async def company_abstract(company_id: str, resolution: int = 0) -> dict[str, object]:
    """Return a Persian introduction for the primary company based on tenant config."""

    from .retrieve.schemas import RetrieveRequest, RetrieveResolution
    from .retrieve.services import retrieval

    return await retrieval(
        RetrieveRequest(
            tenant_id=company_id,
            resolution=RetrieveResolution.MAJOR_TYPE_AND_NAME
            if resolution == 0
            else RetrieveResolution.SELECTED_ENTITIES_AND_MUTUAL_RELATIONS
            if resolution == 1
            else RetrieveResolution.RELATED_ARTIFACTS_DATA
            if resolution == 2
            else RetrieveResolution.RELATED_ARTIFACTS_TEXT,
        )
    )


router.include_router(ingest_router)
router.include_router(retrieve_router)
