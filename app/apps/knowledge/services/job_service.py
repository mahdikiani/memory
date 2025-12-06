"""Job service for managing ingestion jobs."""

import logging
from datetime import datetime
from uuid import uuid4

from apps.knowledge.schemas import IngestJob
from server.db import db_manager

logger = logging.getLogger(__name__)


class JobService:
    """Service for managing ingestion jobs."""

    async def create_job(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
    ) -> str:
        """
        Create a new ingestion job.

        Args:
            tenant_id: Tenant ID
            source_type: Type of knowledge source
            source_id: External source ID

        Returns:
            Job ID

        """
        db = db_manager.get_db()

        job_id = f"ingest_job:{uuid4().hex[:12]}"
        job = IngestJob(
            tenant_id=tenant_id,
            status="queued",
            source_type=source_type,
            source_id=source_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        try:
            result = await db.create(job_id, job.model_dump(exclude={"id"}))
            created_id = (
                result.get("id", job_id) if isinstance(result, dict) else job_id
            )
            logger.info("Created ingestion job: %s", created_id)
        except Exception:
            logger.exception("Failed to create job")
            raise
        return created_id

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status (queued, processing, completed, failed)
            error_message: Optional error message

        """
        db = db_manager.get_db()

        update_data: dict[str, object] = {
            "status": status,
            "updated_at": datetime.now(),
        }

        if error_message:
            update_data["error_message"] = error_message

        if status in ("completed", "failed"):
            update_data["completed_at"] = datetime.now()

        try:
            await db.update(job_id, update_data)
            logger.debug("Updated job %s status to %s", job_id, status)
        except Exception:
            logger.exception("Failed to update job status")
            raise

    async def get_job(self, job_id: str) -> IngestJob | None:
        """
        Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            IngestJob or None if not found

        """
        db = db_manager.get_db()

        try:
            result = await db.select(job_id)
            if result:
                return IngestJob(**result)
        except Exception:
            logger.exception("Failed to get job")
            return None

        return None
