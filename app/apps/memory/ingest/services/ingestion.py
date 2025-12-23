"""Main ingestion helpers (functional) for ingestion processes."""

import asyncio
import logging

from db.models import RecordId

from ...models import Artifact, Entity, Event
from ...relation import Relation
from ..models import IngestJob, IngestStatus
from ..schemas import (
    ContentIngestion,
    EntityIngestion,
    IngestRequest,
    RelationIngestion,
)
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
    tenant_id: RecordId,
    entity: EntityIngestion,
    artifacts: list[Artifact] | None = None,
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
    tenant_id: RecordId,
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


async def upsert_relation(tenant_id: RecordId, relation: RelationIngestion) -> Relation:
    """Upsert a relation using RELATE command."""
    from surrealdb import RecordID

    from db.models import DatabaseManager
    from db.query_executor import execute_query

    db_manager = DatabaseManager()
    db = db_manager.get_db()

    source_id: RecordID = RecordId(relation.from_entity_id).to_record_id()
    target_id: RecordID = RecordId(relation.to_entity_id).to_record_id()
    tenant_id: RecordID = RecordId(tenant_id).to_record_id()
    relation_type = relation.relation_type

    # Check if relation already exists
    # In SurrealDB, edges are stored with 'out' and 'in' fields
    # We need to query using these field names directly
    find_existing_query = (
        "SELECT * FROM relation "
        "WHERE out = $target_id "
        "AND in = $source_id "
        "AND relation_type = $relation_type "
        "AND tenant_id = $tenant_id "
        "AND is_deleted = false "
        "LIMIT 1"
    )

    find_existing_variables = {
        "source_id": source_id,
        "target_id": target_id,
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
        "RELATE $source_id -> relation -> $target_id "
        "SET tenant_id = $tenant_id, "
        "relation_type = $relation_type, "
        "data = $data, "
        "updated_at = time::now(), "
        "is_deleted = false, "
        "created_at = time::now()"
    )

    variables = {
        "source_id": source_id,
        "target_id": target_id,
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
        "WHERE out = $target_id "
        "AND in = $source_id "
        "AND relation_type = $relation_type "
        "AND tenant_id = $tenant_id "
        "AND is_deleted = false "
        "LIMIT 1"
    )

    find_variables = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "tenant_id": tenant_id,
    }

    results = await execute_query(find_query, find_variables)

    if not results:
        logging.info("Find relation query: \n%s\n%s", find_query, results)
        dict_vars = []
        for key, value in find_variables.items():
            dict_vars.append(f"{key} = ({type(value)}) {value!r}")
        logging.info("Find relation variables: \n%s", "\n".join(dict_vars))
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


async def resolve_entity_id(
    entity_id: str,
    entity_mapping: dict[str, str],
    artifact_mapping: dict[str, str],
    tenant_id: RecordId,
    warnings: list[str],
) -> str | None:
    """
    Resolve entity ID from internal ID to database ID.

    Args:
        entity_id: Internal ID or database ID
        entity_mapping: Mapping from internal entity ID to database ID
        artifact_mapping: Mapping from internal artifact ID to database ID
        tenant_id: Tenant ID for database lookup
        warnings: List to append warnings to

    Returns:
        Resolved database ID or None if not found
    """
    # First check entity mapping
    if entity_id in entity_mapping:
        return entity_mapping[entity_id]

    # Then check artifact mapping
    if entity_id in artifact_mapping:
        return artifact_mapping[entity_id]

    # Try to find in database (might be an existing entity ID)
    entity = await Entity.find_one(id=entity_id, tenant_id=tenant_id)
    if entity:
        return str(entity.id)

    # Not found anywhere
    warnings.append(
        f"Entity ID '{entity_id}' not found in payload or database. "
        f"Relation referencing this ID will be skipped."
    )
    return None


async def create_artifacts_with_mapping(
    tenant_id: RecordId,
    contents: list[ContentIngestion],
    uri: str | None,
    sensor_name: str,
) -> tuple[list[Artifact], dict[str, str]]:
    """
    Create artifacts from contents and build mapping from internal ID to database ID.

    Args:
        tenant_id: Tenant ID
        contents: List of content ingestion objects
        uri: URI of the artifact
        sensor_name: Name of the sensor

    Returns:
        Tuple of (artifacts list, mapping dict)
    """
    artifacts: list[Artifact] = []
    artifact_mapping: dict[str, str] = {}

    for content in contents:
        artifact = await Artifact(
            tenant_id=tenant_id,
            uri=uri,
            sensor_name=sensor_name,
            data=content.data,
            raw_text=content.text,
            meta_data=content.meta_data,
        ).save()
        artifacts.append(artifact)
        if content.id:
            artifact_mapping[content.id] = str(artifact.id)

    return artifacts, artifact_mapping


async def upsert_entities_with_mapping(
    tenant_id: RecordId,
    entities: list[EntityIngestion],
    artifacts: list[Artifact],
) -> tuple[list[Entity], dict[str, str]]:
    """
    Upsert entities and build mapping from internal ID to database ID.

    Args:
        tenant_id: Tenant ID
        entities: List of entity ingestion objects
        artifacts: List of artifacts

    Returns:
        Tuple of (entities list, mapping dict)
    """
    saved_entities = await asyncio.gather(*[
        upsert_entity(tenant_id, entity, artifacts) for entity in entities
    ])

    entity_mapping: dict[str, str] = {}
    for entity_ingestion, saved_entity in zip(entities, saved_entities, strict=True):
        entity_mapping[entity_ingestion.id] = str(saved_entity.id)

    return saved_entities, entity_mapping


async def resolve_and_collect_relations(
    payload: IngestRequest,
    entity_mapping: dict[str, str],
    artifact_mapping: dict[str, str],
    warnings: list[str],
) -> list[RelationIngestion]:
    """
    Resolve all relation IDs and collect them into a list.

    Args:
        payload: Ingest request payload
        entity_mapping: Mapping from internal entity ID to database ID
        artifact_mapping: Mapping from internal artifact ID to database ID
        warnings: List to append warnings to

    Returns:
        List of resolved relation ingestion objects
    """
    all_relations: list[RelationIngestion] = []

    # Relations from payload.relations
    for relation in payload.relations:
        from_id = await resolve_entity_id(
            relation.from_entity_id,
            entity_mapping,
            artifact_mapping,
            payload.tenant_id,
            warnings,
        )
        to_id = await resolve_entity_id(
            relation.to_entity_id,
            entity_mapping,
            artifact_mapping,
            payload.tenant_id,
            warnings,
        )
        if from_id and to_id:
            relation.from_entity_id = from_id
            relation.to_entity_id = to_id
            all_relations.append(relation)

    # Relations from content.relations
    for content in payload.contents:
        if not content.id:
            continue
        for relation in content.relations:
            from_id = await resolve_entity_id(
                content.id,
                entity_mapping,
                artifact_mapping,
                payload.tenant_id,
                warnings,
            )
            to_id = await resolve_entity_id(
                relation.to_entity_id,
                entity_mapping,
                artifact_mapping,
                payload.tenant_id,
                warnings,
            )
            if from_id and to_id:
                relation_ingestion = RelationIngestion(
                    from_entity_id=from_id,
                    to_entity_id=to_id,
                    relation_type=relation.relation_type,
                    data=relation.data,
                    meta_data=relation.meta_data,
                )
                all_relations.append(relation_ingestion)

    return all_relations


async def upsert_all_relations(
    tenant_id: RecordId, relations: list[RelationIngestion]
) -> list[Relation]:
    """
    Upsert all relations.

    Args:
        tenant_id: Tenant ID
        relations: List of relation ingestion objects

    Returns:
        List of saved relation objects
    """
    return await asyncio.gather(*[
        upsert_relation(tenant_id, relation) for relation in relations
    ])


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
