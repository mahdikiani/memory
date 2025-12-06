"""Knowledge source service for managing knowledge sources."""

import logging
from datetime import datetime

from server.db import db_manager

from ..models import KnowledgeSource

logger = logging.getLogger(__name__)


class KnowledgeSourceService:
    """Service for managing knowledge sources."""

    async def create_source(
        self,
        tenant_id: str,
        source_type: str,
        source_id: str,
        sensor_name: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> str:
        """
        Create a new knowledge source.

        Args:
            tenant_id: Tenant ID
            source_type: Type of source
            source_id: External source ID
            sensor_name: Name of the sensor/service
            metadata: Additional metadata

        Returns:
            Created source record ID

        """
        db = db_manager.get_db()

        source = KnowledgeSource(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            sensor_name=sensor_name,
            meta_data=metadata or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Generate record ID
        record_id = f"knowledge_source:{tenant_id}:{source_id}"

        try:
            result = await db.create(record_id, source.model_dump(exclude={"id"}))
            logger.info("Created knowledge source: %s", record_id)
            return (
                result.get("id", record_id) if isinstance(result, dict) else record_id
            )
        except Exception:
            logger.exception("Failed to create knowledge source")
            raise

    async def get_source(
        self, tenant_id: str, source_id: str
    ) -> KnowledgeSource | None:
        """
        Get a knowledge source by ID.

        Args:
            tenant_id: Tenant ID
            source_id: External source ID

        Returns:
            KnowledgeSource or None if not found

        """
        db = db_manager.get_db()
        record_id = f"knowledge_source:{tenant_id}:{source_id}"

        try:
            result = await db.select(record_id)
            if result:
                return KnowledgeSource(**result)
        except Exception:
            logger.exception("Failed to get knowledge source")
            return None

        return None

    async def update_source(
        self,
        tenant_id: str,
        source_id: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """
        Update knowledge source metadata.

        Args:
            tenant_id: Tenant ID
            source_id: External source ID
            metadata: Updated metadata

        """
        db = db_manager.get_db()
        record_id = f"knowledge_source:{tenant_id}:{source_id}"

        try:
            update_data: dict[str, object] = {"updated_at": datetime.now()}
            if metadata is not None:
                update_data["meta_data"] = metadata

            await db.update(record_id, update_data)
            logger.debug("Updated knowledge source: %s", record_id)
        except Exception:
            logger.exception("Failed to update knowledge source")
            raise
