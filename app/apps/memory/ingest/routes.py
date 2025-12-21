"""Routes for ingest endpoints."""

from fastapi import APIRouter

from ..exceptions import BaseHTTPException
from ..models import Company
from .schemas import IngestionResult, IngestRequest
from .services.ingestion import (
    create_artifacts_with_mapping,
    resolve_and_collect_relations,
    upsert_all_relations,
    upsert_entities_with_mapping,
)
from .services.job import create_ingestion_jobs

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
async def ingest(payload: IngestRequest) -> IngestionResult:
    """Ingest a user-confirmed entity without LLM processing."""

    company: Company | None = await Company.get_by_id(
        id=payload.tenant_id, company_id=payload.company_id
    )
    if not company:
        raise BaseHTTPException(
            status_code=404,
            error="company_not_found",
            detail="Company not found",
        )
    payload.tenant_id = company.id

    warnings: list[str] = []

    artifacts, artifact_mapping = await create_artifacts_with_mapping(
        payload.tenant_id,
        payload.contents,
        payload.uri,
        payload.sensor_name,
    )

    entities, entity_mapping = await upsert_entities_with_mapping(
        payload.tenant_id,
        payload.entities,
        artifacts,
    )

    all_relations = await resolve_and_collect_relations(
        payload,
        entity_mapping,
        artifact_mapping,
        warnings,
    )

    relations = await upsert_all_relations(payload.tenant_id, all_relations)

    jobs = await create_ingestion_jobs(artifacts=artifacts)
    return IngestionResult(
        job_ids=[job.id for job, _ in jobs],
        entities=entities,
        relations=relations,
        warnings=warnings,
    )
