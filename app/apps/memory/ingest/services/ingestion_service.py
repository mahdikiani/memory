"""Main ingestion service orchestrating the ingestion process."""

import logging

from server.config import Settings

from ..job_service import JobService
from ..knowledge_source_service import KnowledgeSourceService
from ..models import IngestionResult
from ..processors.entity_processor import save_entities
from ..processors.relation_processor import save_relations
from ..services.chunk_service import save_chunks
from ..services.preprocessor import preprocess_chunks
from ..services.structured_processor import (
    process_structured_entity,
    process_structured_relation,
)
from ..services.unstructured_processor import process_unstructured

logger = logging.getLogger(__name__)


class IngestionService:
    """Main service for orchestrating ingestion processes."""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize ingestion service.

        Args:
            settings: Application settings

        """
        self.settings = settings
        self.knowledge_source_service = KnowledgeSourceService()
        self.job_service = JobService()

    async def ingest_unstructured(
        self,
        content: str,
        source_type: str,
        source_id: str,
        tenant_id: str,
        metadata: dict[str, object] | None = None,
        sensor_name: str | None = None,
    ) -> IngestionResult:
        """
        Ingest unstructured content (text that needs analysis).

        Args:
            content: Text content to ingest
            source_type: Type of knowledge source
            source_id: External source ID
            tenant_id: Tenant ID
            metadata: Additional metadata
            sensor_name: Name of the sensor/service

        Returns:
            IngestionResult with job_id and counts

        """
        # Step 1: Create or get knowledge source
        source_record_id = await self.knowledge_source_service.create_source(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            sensor_name=sensor_name,
            metadata=metadata,
        )

        # Step 2: Create ingestion job
        job_id = await self.job_service.create_job(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
        )

        try:
            # Step 3: Process unstructured content
            chunks, entities, relations = await process_unstructured(
                content=content,
                tenant_id=tenant_id,
                source_id=source_record_id,
                metadata=metadata,
                settings=self.settings,
            )

            # Step 4: Preprocess chunks (generate embeddings)
            preprocessed_chunks = await preprocess_chunks(chunks, self.settings)

            # Step 5: Save chunks
            chunks_count = await save_chunks(preprocessed_chunks, source_record_id)

            # Step 6: Save entities
            entities_count = await save_entities(entities, tenant_id, source_record_id)

            # Step 7: Save relations
            relations_count = await save_relations(
                relations, tenant_id, source_record_id
            )

            # Step 8: Update job status to completed
            await self.job_service.update_job_status(job_id, "completed")

            logger.info(
                "Completed ingestion job %s: %d chunks, %d entities, %d relations",
                job_id,
                chunks_count,
                entities_count,
                relations_count,
            )

            return IngestionResult(
                job_id=job_id,
                chunks_count=chunks_count,
                entities_count=entities_count,
                relations_count=relations_count,
            )

        except Exception:
            logger.exception("Failed to ingest unstructured content")
            await self.job_service.update_job_status(
                job_id, "failed", error_message="Ingestion failed"
            )
            raise

    async def ingest_structured_entity(
        self,
        entity_data: dict[str, object],
        tenant_id: str,
        source_id: str,
        source_type: str,
        sensor_name: str | None = None,
    ) -> str:
        """
        Ingest a structured entity (user-confirmed, no analysis needed).

        Args:
            entity_data: Entity data (entity_type, name, attributes)
            tenant_id: Tenant ID
            source_id: External source ID
            source_type: Type of knowledge source
            sensor_name: Name of the sensor/service

        Returns:
            Entity record ID

        """
        # Create or get knowledge source
        source_record_id = await self.knowledge_source_service.create_source(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            sensor_name=sensor_name,
        )

        # Process and save structured entity
        entity_id = await process_structured_entity(
            entity_data=entity_data,
            tenant_id=tenant_id,
            source_id=source_record_id,
        )

        logger.info("Ingested structured entity: %s", entity_id)
        return entity_id

    async def ingest_structured_relation(
        self,
        relation_data: dict[str, object],
        tenant_id: str,
        source_id: str,
        source_type: str,
        sensor_name: str | None = None,
    ) -> str:
        """
        Ingest a structured relation (user-confirmed, no analysis needed).

        Args:
            relation_data: Relation data
                           (from_entity_id, to_entity_id, relation_type, attributes)
            tenant_id: Tenant ID
            source_id: External source ID
            source_type: Type of knowledge source
            sensor_name: Name of the sensor/service

        Returns:
            Relation record ID

        """
        # Create or get knowledge source
        source_record_id = await self.knowledge_source_service.create_source(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            sensor_name=sensor_name,
        )

        # Process and save structured relation
        relation_id = await process_structured_relation(
            relation_data=relation_data,
            tenant_id=tenant_id,
            source_id=source_record_id,
        )

        logger.info("Ingested structured relation: %s", relation_id)
        return relation_id
