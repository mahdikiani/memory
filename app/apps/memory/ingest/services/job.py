"""Functional helpers for ingestion jobs with Redis queue."""

import asyncio
import logging
from datetime import datetime

from utils.queue_manager import enqueue

from ...models import Artifact
from ..models import IngestJob, IngestStatus

logger = logging.getLogger(__name__)


async def create_artifact_processing_job(artifact: Artifact) -> tuple[IngestJob, int]:
    """Create an artifact job."""
    job = await IngestJob(
        tenant_id=artifact.tenant_id,
        status=IngestStatus.QUEUED,
        artifact_id=artifact.id,
    ).save()

    index = await enqueue(job.model_dump(), queue_name="ingestion")
    return job, index


async def create_ingestion_jobs(
    artifacts: list[Artifact],
) -> list[tuple[IngestJob, int]]:
    """
    Create an ingestion job.

    It create a knowledge source record and an ingestion job record.
    Then add the job to the ingestion queue.
    """

    jobs = await asyncio.gather(*[
        create_artifact_processing_job(artifact)
        for artifact in artifacts
    ])
    return jobs


async def update_job_status(
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    """Update job status using model persistence."""
    job = await IngestJob.find_one(id=job_id)
    if not job:
        logger.warning("Job %s not found for status update", job_id)
        return

    job.status = status

    if error_message:
        job.error_message = error_message

    if status in ("completed", "failed"):
        job.completed_at = datetime.now()

    await job.save()
    logger.debug("Updated job %s status to %s", job_id, status)
