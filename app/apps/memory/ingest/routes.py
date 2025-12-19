"""Routes for ingest endpoints."""

import asyncio

from fastapi import APIRouter

from ..models import Artifact
from .schemas import IngestionResult, IngestRequest
from .services.ingestion import upsert_entity, upsert_relation
from .services.job import create_ingestion_jobs

router = APIRouter(tags=["ingest"])


@router.post("/ingest")
async def ingest(payload: IngestRequest) -> IngestionResult:
    """Ingest a user-confirmed entity without LLM processing."""

    # Create artifact if we have contents or uri/sensor_name
    artifacts: list[Artifact] = []
    for content in payload.contents:
        # Create artifact for structured ingestion
        artifact = await Artifact(
            tenant_id=payload.tenant_id,
            uri=payload.uri,
            sensor_name=payload.sensor_name,
            raw_text=content,
            meta_data=payload.meta_data,
        ).save()
        artifacts.append(artifact)

    entities = await asyncio.gather(*[
        upsert_entity(
            payload.tenant_id,
            entity,
            artifacts,
        )
        for entity in payload.entities
    ])
    relations = await asyncio.gather(
        *(
            [
                upsert_relation(payload.tenant_id, relation, artifacts)
                for relation in payload.relations
            ]
            + [
                upsert_relation(payload.tenant_id, relation, artifacts)
                for entity in payload.entities
                for relation in entity.relations
            ]
        )
    )
    jobs = await create_ingestion_jobs(artifacts=artifacts)
    return IngestionResult(
        job_ids=[job.id for job, _ in jobs],
        entities=entities,
        relations=relations,
    )
