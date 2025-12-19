"""Routes for retrieve endpoints."""

from fastapi import APIRouter

from .schemas import (
    RetrieveRequest,
    RetrieveResponse,
)
from .services import retrieval

router = APIRouter(tags=["retrieve"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(payload: RetrieveRequest) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""

    return await retrieval(payload)
