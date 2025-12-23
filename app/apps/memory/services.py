"""Service for managing tenant-specific configurations."""

import logging

from .exceptions import BaseHTTPException
from .models import Company
from .schemas import CompanyCreateSchema

logger = logging.getLogger(__name__)


async def create_company(data: CompanyCreateSchema, override: bool = False) -> Company:
    """Create or update tenant configuration."""

    # Get existing config or create new
    company = await Company.find_one(company_id=data.company_id)
    if company and not override:
        raise BaseHTTPException(
            status_code=409,
            error="company_id_already_exists",
            detail="Company with this company_id already exists",
        )
    elif company:
        await company.update(**data.model_dump(exclude_unset=True))
    else:
        company = Company.model_validate(data)

    return await company.save()
