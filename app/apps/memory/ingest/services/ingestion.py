"""Main ingestion helpers (functional) for ingestion processes."""

import logging

from db.models import RecordId

from ...models import Artifact, Entity, Event
from ...relation import Relation
from ..models import IngestJob, IngestStatus
from ..schemas import EntityIngestion, RelationIngestion
from .text_processor import TextProcessor

logger = logging.getLogger(__name__)


async def create_entity_event(
    entity: Entity,
    artifacts: list[Artifact],
    event_type: str,
    data: dict[str, object],
) -> Event:
    """Create an entity event."""

    event = Event(
        tenant_id=entity.tenant_id,
        entity_id=entity.id,
        artifact_ids=[RecordId(artifact.id) for artifact in artifacts],
        event_type=event_type,
        data=data,
    )
    return await event.save()


async def update_entity(
    entity: Entity,
    data: EntityIngestion,
    artifacts: list[Artifact] | None = None,
) -> Entity:
    """Update an entity."""

    update_fields = data.model_dump(exclude_unset=True)
    updated_data = await entity.update(**update_fields)
    saved_entity = await entity.save()
    await create_entity_event(
        saved_entity,
        artifacts or [],
        "entity_updated",
        updated_data,
    )

    return saved_entity


async def create_entity(
    tenant_id: str, entity: EntityIngestion, artifacts: list[Artifact] | None = None
) -> Entity:
    """Create a new entity."""

    new_entity = Entity(
        tenant_id=tenant_id,
        entity_type=entity.entity_type,
        name=entity.name,
        data=entity.data,
    )
    saved_entity = await new_entity.save()

    await create_entity_event(
        saved_entity,
        artifacts or [],
        "entity_created",
        new_entity.model_dump(),
    )

    return saved_entity


async def upsert_entity(
    tenant_id: str,
    entity: EntityIngestion,
    artifacts: list[Artifact] | None = None,
) -> Entity:
    """Upsert an entity."""

    if entity.entity_id:
        existing_entity = await Entity.find_one(id=entity.entity_id)
        if existing_entity:
            return await update_entity(existing_entity, entity, artifacts)

    return await create_entity(tenant_id, entity, artifacts)


async def update_relation(relation: Relation, data: RelationIngestion) -> Relation:
    """Update a relation."""

    update_fields = data.model_dump(exclude_unset=True)
    # Map from_entity_id to source_id and to_entity_id to target_id
    if "from_entity_id" in update_fields:
        update_fields["source_id"] = update_fields.pop("from_entity_id")
    if "to_entity_id" in update_fields:
        update_fields["target_id"] = update_fields.pop("to_entity_id")

    for field, value in update_fields.items():
        if hasattr(relation, field):
            setattr(relation, field, value)

    return await relation.save()


async def upsert_relation(tenant_id: str, relation: RelationIngestion) -> Relation:
    """Upsert a relation using RELATE command."""
    from db.models import DatabaseManager
    from db.query_executor import execute_query

    db_manager = DatabaseManager()
    db = db_manager.get_db()

    source_id = RecordId(relation.from_entity_id)
    target_id = RecordId(relation.to_entity_id)
    relation_type = relation.relation_type

    # Check if relation already exists
    # In SurrealDB, edges are stored with 'out' and 'in' fields
    # We need to query using these field names directly
    find_existing_query = (
        "SELECT * FROM relation "
        "WHERE out = $source_id "
        "AND `in` = $target_id "
        "AND relation_type = $relation_type "
        "AND tenant_id = $tenant_id "
        "AND is_deleted = false "
        "LIMIT 1"
    )

    find_existing_variables = {
        "source_id": str(source_id),
        "target_id": str(target_id),
        "relation_type": relation_type,
        "tenant_id": tenant_id,
    }

    existing_results = await execute_query(find_existing_query, find_existing_variables)

    # If relation exists, update it
    if existing_results:
        relation_data = existing_results[0].copy()
        # Map 'out' to source_id and 'in' to target_id for the model
        if "out" in relation_data:
            relation_data["source_id"] = relation_data.pop("out")
        if "in" in relation_data:
            relation_data["target_id"] = relation_data.pop("in")

        existing_relation = Relation(**relation_data)
        return await update_relation(existing_relation, relation)

    # If relation doesn't exist, create it using RELATE
    # In SurrealDB, RELATE creates an edge in a table
    # Use relation:{relation_type} to store in "relation" table
    # with relation_type as edge type
    relate_query = (
        f"RELATE {source_id} -> {relation_type} -> {target_id} "
        f"SET tenant_id = $tenant_id, "
        f"relation_type = $relation_type, "
        f"data = $data, "
        f"updated_at = time::now(), "
        f"is_deleted = false, "
        f"created_at = time::now()"
    )

    variables = {
        "tenant_id": tenant_id,
        "relation_type": relation_type,
        "data": relation.data or {},
    }

    # Execute RELATE command
    await db.query(relate_query, variables)

    # Find the relation record we just created
    # Relations are stored with 'out' and 'in' fields in SurrealDB
    find_query = (
        "SELECT * FROM relation "
        "WHERE out = $source_id "
        "AND `in` = $target_id "
        "AND relation_type = $relation_type "
        "AND tenant_id = $tenant_id "
        "AND is_deleted = false "
        "LIMIT 1"
    )

    find_variables = {
        "source_id": str(source_id),
        "target_id": str(target_id),
        "relation_type": relation_type,
        "tenant_id": tenant_id,
    }

    results = await execute_query(find_query, find_variables)

    if not results:
        raise ValueError(
            f"Failed to find relation after RELATE: "
            f"{source_id} -> {relation_type} -> {target_id}"
        )

    # Deserialize the result into Relation model
    # Map 'out' to source_id and 'in' to target_id for the model
    relation_data = results[0].copy()
    if "out" in relation_data:
        relation_data["source_id"] = relation_data.pop("out")
    if "in" in relation_data:
        relation_data["target_id"] = relation_data.pop("in")

    return Relation(**relation_data)


async def ingest(job_dict: dict[str, object]) -> None:
    """
    Ingest a job.

    It will process the job. If the job was cancelled earlier,
    the task will be failed. Otherwise, it will update the job
    status.
    The task is loading the artifact and chunking the text and
    creating embeddings for the chunks and store the indexed
    chunks in the database.

    Args:
        job_dict: Job dictionary
    """

    from ...models import Artifact

    job_id = job_dict.get("id")
    if not job_id:
        logger.error("Job ID not found in the dictionary")
        return

    job = await IngestJob.find_one(id=job_id)
    if not job:
        logger.error("Job %s not found", job_id)
        return

    if not job.status.is_queued():
        logger.warning("Job %s is not queued", job_id)
        return

    job.status = IngestStatus.PROCESSING
    await job.save()

    artifact = await Artifact.find_one(id=job.artifact_id)
    if not artifact:
        logger.error("Artifact %s not found", job.artifact_id)
        return

    text_processor = TextProcessor()
    meta_data = (artifact.meta_data or {}) | (job.meta_data or {})

    await text_processor.create_chunks(
        tenant_id=artifact.tenant_id,
        text=artifact.raw_text,
        artifact_id=artifact.id,
        meta_data=meta_data,
    )
    job.status = IngestStatus.COMPLETED
    await job.save()
    return
