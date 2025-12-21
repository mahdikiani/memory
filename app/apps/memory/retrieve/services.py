"""Services for retrieve endpoints."""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate

from prompts.services import PromptService
from server.config import Settings

from ..exceptions import BaseHTTPException
from ..models import Artifact, ArtifactChunk, Company, Entity
from ..relation import Relation
from ..utils.embedding import generate_embedding
from ..utils.openai_client import get_client_and_model
from .schemas import (
    ArtifactWithChunks,
    RetrieveRequest,
    RetrieveResolution,
    RetrieveResponse,
)

logger = logging.getLogger(__name__)


def build_introduction(company: Company) -> list[str]:
    """Build Persian introduction based on company data."""
    intro = [f"{company.name} یک شرکت است با شناسه ملی {company.company_id}."]
    if company.data.get("industry"):
        intro.append(f"در حوزه {company.data.get('industry')} فعالیت می‌کند")
    if company.data.get("description"):
        intro.append(f"توضیحات: {company.data.get('description')}.")
    return intro


def retrieve_type_only(company: Company, payload: RetrieveRequest) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""

    intro = build_introduction(company)
    intro.append(f"در این شرکت موجودیت‌های {company.entity_types} وجود دارند.")
    intro.append(f"در این شرکت روابط {company.relation_types} وجود دارند.")
    intro.append(".")

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=[],
        relations=[],
        artifacts=[],
        context="\n".join(intro),
    )


async def retrieve_major_type_and_name(
    company: Company, payload: RetrieveRequest
) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""

    # Build Persian introduction based on resolution level
    intro = build_introduction(company)

    # Medium detail with description
    all_entities = []
    for entity_type in company.entity_types:
        entities = await Entity.find_many(
            skip=0, limit=100, tenant_id=company.id, entity_type=entity_type
        )
        if not entities:
            continue

        names = "، ".join(entity.name for entity in entities)
        intro.append(
            " ".join([
                "در این شرکت مهم‌ترین موجودیت‌های نوع",
                entity_type,
                "شامل این موارد است: ",
                names,
            ])
        )
        all_entities.extend(entities)

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=all_entities,
        relations=[],
        artifacts=[],
        context="\n".join(intro),
    )


async def retrieve_selected_entities(
    company: Company, payload: RetrieveRequest
) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""

    intro = build_introduction(company)

    selected_entities = []
    entity_jsons = []

    for entity_id in payload.entity_ids:
        entity = await Entity.get_by_id(id=entity_id)
        if not entity:
            continue
        selected_entities.append(entity)

        # Get JSON representation of entity using Pydantic
        entity_json = entity.model_dump_json(
            exclude={
                "id",
                "tenant_id",
                "created_at",
                "updated_at",
                "is_deleted",
                "meta_data",
                "user_permissions",
                "group_permissions",
                "public_permission",
            },
            exclude_none=True,
        )
        entity_jsons.append(entity_json)

    intro.extend(entity_jsons)
    intro.append(".")

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=selected_entities,
        relations=[],
        artifacts=[],
        context="\n".join(intro) if intro else None,
    )


async def _get_entities_and_ids(
    entity_ids: list[str],
) -> tuple[list[Entity], list[str], list[str]]:
    """Get entities and their IDs and JSON representations."""
    selected_entities = []
    entity_jsons = []
    entity_id_strings = []

    for entity_id in entity_ids:
        entity = await Entity.get_by_id(id=entity_id)
        if not entity:
            continue
        selected_entities.append(entity)
        entity_id_strings.append(str(entity.id))

        # Get JSON representation of entity using Pydantic
        entity_json = entity.model_dump_json(
            exclude={
                "id",
                "tenant_id",
                "created_at",
                "updated_at",
                "is_deleted",
                "meta_data",
                "user_permissions",
                "group_permissions",
                "public_permission",
            },
            exclude_none=True,
        )
        entity_jsons.append(entity_json)

    return selected_entities, entity_id_strings, entity_jsons


async def _find_mutual_relations(
    company: Company, entity_ids: list[str]
) -> list[Relation]:
    """Find relations where both source and target are in the entity IDs."""
    from db.query_executor import execute_query

    mutual_relations: list[Relation] = []
    relation_types = company.relation_types or []

    for relation_type in relation_types:
        # Query relations where both source and target are in entity IDs
        # In SurrealDB, edges have 'out' (source) and 'in' (target) fields
        Relation._validate_table_name(relation_type)
        query = (
            f"SELECT * FROM {relation_type} "  # noqa: S608
            "WHERE tenant_id = $tenant_id "
            "AND is_deleted = false "
            "AND out IN $entity_ids "
            "AND `in` IN $entity_ids"
        )

        variables = {
            "tenant_id": company.id,
            "entity_ids": entity_ids,
        }

        try:
            rows = await execute_query(query, variables)
            for row in rows:
                # Map 'out' to source_id and 'in' to target_id
                relation_data = row.copy()
                if "out" in relation_data:
                    relation_data["source_id"] = relation_data.pop("out")
                if "in" in relation_data:
                    relation_data["target_id"] = relation_data.pop("in")
                try:
                    relation = Relation(**relation_data)
                    mutual_relations.append(relation)
                except Exception:
                    logger.warning("Failed to create Relation from row: %s", row)
                    continue
        except Exception:
            logger.exception("Failed to query relations for type: %s", relation_type)
            continue

    return mutual_relations


async def _build_artifact_entity_mapping(
    company: Company, entity_ids: list[str], relation_type: str
) -> dict[str, set[str]]:
    """
    Build mapping of artifact IDs to connected entity IDs for a relation type.

    Args:
        company: Company object
        entity_ids: List of entity IDs
        relation_type: Type of relation to query

    Returns:
        Dictionary mapping artifact_id to set of connected entity_ids
    """
    from db.query_executor import execute_query

    artifact_entity_map: dict[str, set[str]] = {}
    Relation._validate_table_name(relation_type)

    query = (
        f"SELECT * FROM {relation_type} "  # noqa: S608
        "WHERE tenant_id = $tenant_id "
        "AND is_deleted = false "
        "AND ((out IN $entity_ids AND `in` LIKE 'artifact:%') "
        "OR (`in` IN $entity_ids AND out LIKE 'artifact:%'))"
    )

    variables = {
        "tenant_id": company.id,
        "entity_ids": entity_ids,
    }

    try:
        rows = await execute_query(query, variables)
        for row in rows:
            source_id = str(row.get("out", ""))
            target_id = str(row.get("in", ""))

            # Check if source is entity and target is artifact
            if source_id in entity_ids and target_id.startswith("artifact:"):
                artifact_id = target_id
                if artifact_id not in artifact_entity_map:
                    artifact_entity_map[artifact_id] = set()
                artifact_entity_map[artifact_id].add(source_id)

            # Check if target is entity and source is artifact
            if target_id in entity_ids and source_id.startswith("artifact:"):
                artifact_id = source_id
                if artifact_id not in artifact_entity_map:
                    artifact_entity_map[artifact_id] = set()
                artifact_entity_map[artifact_id].add(target_id)

    except Exception:
        logger.exception("Failed to query relations for type: %s", relation_type)

    return artifact_entity_map


async def _fetch_artifacts_by_ids(
    company: Company, artifact_ids: list[str]
) -> list[Artifact]:
    """
    Fetch artifacts by their IDs.

    Args:
        company: Company object
        artifact_ids: List of artifact IDs

    Returns:
        List of fetched artifacts
    """
    artifacts: list[Artifact] = []
    for artifact_id in artifact_ids:
        try:
            artifact = await Artifact.find_one(id=artifact_id, tenant_id=company.id)
            if artifact:
                artifacts.append(artifact)
        except Exception:
            logger.warning("Failed to fetch artifact: %s", artifact_id)
            continue

    return artifacts


async def _find_artifacts_connected_to_artifacts(
    company: Company, artifact_ids: list[str]
) -> list[str]:
    """
    Find artifact IDs that are connected to the given artifact IDs.

    Args:
        company: Company object
        artifact_ids: List of artifact IDs to find connections for

    Returns:
        List of artifact IDs connected to the given artifacts
    """
    from db.query_executor import execute_query

    if not artifact_ids:
        return []

    connected_artifact_ids: set[str] = set()
    relation_types = company.relation_types or []

    for relation_type in relation_types:
        Relation._validate_table_name(relation_type)
        # Query relations where source or target is in artifact_ids
        # and the other side is also an artifact
        query = (
            f"SELECT * FROM {relation_type} "  # noqa: S608
            "WHERE tenant_id = $tenant_id "
            "AND is_deleted = false "
            "AND ((out IN $artifact_ids AND `in` LIKE 'artifact:%') "
            "OR (`in` IN $artifact_ids AND out LIKE 'artifact:%'))"
        )

        variables = {
            "tenant_id": company.id,
            "artifact_ids": artifact_ids,
        }

        try:
            rows = await execute_query(query, variables)
            for row in rows:
                source_id = str(row.get("out", ""))
                target_id = str(row.get("in", ""))

                # Check if source is in artifact_ids and target is artifact
                if source_id in artifact_ids and target_id.startswith("artifact:"):
                    connected_artifact_ids.add(target_id)

                # Check if target is in artifact_ids and source is artifact
                if target_id in artifact_ids and source_id.startswith("artifact:"):
                    connected_artifact_ids.add(source_id)

        except Exception:
            logger.exception("Failed to query relations for type: %s", relation_type)
            continue

    return list(connected_artifact_ids)


async def _find_artifacts_connected_to_entities(
    company: Company, entity_ids: list[str]
) -> list[Artifact]:
    """
    Find artifacts connected to entities and their related artifacts.

    Finds artifacts that are connected to at least two entities from the entity
    list, and also finds artifacts connected to those artifacts.

    Args:
        company: Company object
        entity_ids: List of entity IDs

    Returns:
        List of artifacts connected to at least two entities and their
        connected artifacts
    """
    if not entity_ids:
        return []

    # Track which artifacts are connected to which entities
    artifact_entity_map: dict[str, set[str]] = {}  # artifact_id -> set of entity_ids
    relation_types = company.relation_types or []

    for relation_type in relation_types:
        mapping = await _build_artifact_entity_mapping(
            company, entity_ids, relation_type
        )
        # Merge mappings
        for artifact_id, connected_entities in mapping.items():
            if artifact_id not in artifact_entity_map:
                artifact_entity_map[artifact_id] = set()
            artifact_entity_map[artifact_id].update(connected_entities)

    # Filter artifacts that are connected to at least two entities
    connected_artifact_ids = [
        artifact_id
        for artifact_id, connected_entities in artifact_entity_map.items()
        if len(connected_entities) >= 2
    ]

    if not connected_artifact_ids:
        return []

    # Find artifacts connected to these artifacts
    related_artifact_ids = await _find_artifacts_connected_to_artifacts(
        company, connected_artifact_ids
    )

    # Combine all artifact IDs (remove duplicates)
    all_artifact_ids = list(set(connected_artifact_ids + related_artifact_ids))

    return await _fetch_artifacts_by_ids(company, all_artifact_ids)


def _get_relation_jsons(relations: list[Relation]) -> list[str]:
    """Get JSON representations of relations."""
    relation_jsons = []
    for relation in relations:
        relation_json = relation.model_dump_json(
            exclude={
                "id",
                "tenant_id",
                "created_at",
                "updated_at",
                "is_deleted",
                "meta_data",
                "user_permissions",
                "group_permissions",
                "public_permission",
            },
            exclude_none=True,
        )
        relation_jsons.append(relation_json)
    return relation_jsons


async def retrieve_selected_entities_and_mutual_relations(
    company: Company,
    payload: RetrieveRequest,
) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""
    intro = build_introduction(company)

    # Get selected entities
    if not payload.entity_ids:
        return RetrieveResponse(
            tenant_id=company.id,
            company_id=company.company_id,
            entities=[],
            relations=[],
            artifacts=[],
            context="\n".join(intro) if intro else None,
        )

    selected_entities, entity_ids, entity_jsons = await _get_entities_and_ids(
        payload.entity_ids
    )

    # Find mutual relations
    mutual_relations = await _find_mutual_relations(company, entity_ids)

    # Find artifacts connected to at least two entities
    connected_artifacts = await _find_artifacts_connected_to_entities(
        company, entity_ids
    )

    # Build context with entities and relations
    intro.extend(entity_jsons)

    if mutual_relations:
        relation_jsons = _get_relation_jsons(mutual_relations)
        intro.extend(relation_jsons)

    intro.append(".")

    # Convert artifacts to ArtifactWithChunks format
    artifacts_with_chunks = [
        ArtifactWithChunks(artifact=artifact, chunks=[])
        for artifact in connected_artifacts
    ]

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=selected_entities,
        relations=mutual_relations,
        artifacts=artifacts_with_chunks,
        context="\n".join(intro) if intro else None,
    )


async def _extract_entities_from_text(
    text: str, company_context: str, settings: Settings | None = None
) -> list[dict[str, object]]:
    """Extract entities from text using LLM."""
    if settings is None:
        settings = Settings()

    try:
        prompt_service = PromptService(settings)
        prompt_config = await prompt_service.get_prompt("entity_extraction")
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_config["system"]),
            ("human", prompt_config["user"]),
        ])

        # Combine company context with user question
        full_text = f"{company_context}\n\n{text}"

        messages = prompt.format_messages(text=full_text)
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from LLM for entity extraction")
            return []

        result = json.loads(content)
        # Handle both array and object with entities key
        if isinstance(result, list):
            entities = result
        elif isinstance(result, dict) and "entities" in result:
            entities = result["entities"]
        else:
            entities = []

        logger.debug("Extracted %d entities from text", len(entities))

    except Exception:
        logger.exception("Failed to extract entities from text")
        return []

    return entities


async def _find_entities_from_extracted(
    company: Company, extracted_entities: list[dict[str, object]]
) -> tuple[list[Entity], list[str]]:
    """Find matching entities in database from extracted entities."""
    found_entities: list[Entity] = []
    entity_ids: list[str] = []

    for extracted_entity in extracted_entities:
        entity_name = extracted_entity.get("name", "")
        entity_type = extracted_entity.get("entity_type", "")

        if not entity_name:
            continue

        # Try to find entity by name and type
        search_filters: dict[str, object] = {
            "tenant_id": company.id,
            "name": entity_name,
        }
        if entity_type:
            search_filters["entity_type"] = entity_type

        entity = await Entity.find_one(**search_filters)
        if entity and entity.id:
            found_entities.append(entity)
            entity_ids.append(str(entity.id))

    return found_entities, entity_ids


def _process_search_results(
    search_results: dict[str, list[dict[str, object]]],
) -> list[ArtifactChunk]:
    """Process search results and convert to ArtifactChunk objects."""
    chunks: list[ArtifactChunk] = []
    chunk_ids_seen = set()

    # Process main results (fulltext + vector)
    for row in search_results.get("main", []):
        chunk_id = row.get("id")
        if chunk_id and chunk_id not in chunk_ids_seen:
            try:
                chunk = ArtifactChunk(**row)
                chunks.append(chunk)
                chunk_ids_seen.add(chunk_id)
            except Exception:
                logger.warning("Failed to create ArtifactChunk from row: %s", row)
                continue

    # Process graph results if any
    for row in search_results.get("graph", []):
        chunk_id = row.get("id")
        if chunk_id and chunk_id not in chunk_ids_seen:
            try:
                chunk = ArtifactChunk(**row)
                chunks.append(chunk)
                chunk_ids_seen.add(chunk_id)
            except Exception:
                logger.warning("Failed to create ArtifactChunk from graph row: %s", row)
                continue

    return chunks


async def _group_chunks_by_artifact(
    chunks: list[ArtifactChunk],
) -> list[ArtifactWithChunks]:
    """Group chunks by artifact_id and fetch artifacts."""
    artifacts_dict: dict[str, ArtifactWithChunks] = {}

    for chunk in chunks:
        artifact_id = str(chunk.artifact_id) if chunk.artifact_id else None
        if not artifact_id:
            continue

        # Fetch artifact if not already fetched
        if artifact_id not in artifacts_dict:
            artifact = await Artifact.get_by_id(id=artifact_id)
            if artifact:
                artifacts_dict[artifact_id] = ArtifactWithChunks(
                    artifact=artifact, chunks=[]
                )
            else:
                logger.warning("Artifact not found for chunk: %s", artifact_id)
                continue

        # Add chunk to artifact
        artifacts_dict[artifact_id].chunks.append(chunk)

    return list(artifacts_dict.values())


async def _search_artifact_chunks(
    company: Company,
    query_text: str,
    query_embedding: list[float],
    entity_ids: list[str] | None,
) -> list[ArtifactWithChunks]:
    """Perform hybrid search on artifact chunks and group by artifact."""
    from db.query_executor import execute_combined_query

    search_results = await execute_combined_query(
        tenant_id=company.id,
        table="artifact_chunk",
        fulltext_query=query_text,
        vector_embedding=query_embedding,
        graph_entity_ids=entity_ids,
        graph_min_depth=1,
        graph_max_depth=2,
        limit=20,
    )

    chunks = _process_search_results(search_results)
    return await _group_chunks_by_artifact(chunks)


def _build_result_json(
    company: Company,
    entities: list[Entity],
    artifacts_with_chunks: list[ArtifactWithChunks],
) -> str:
    """Build JSON output text from results."""
    intro = build_introduction(company)
    result_data = {
        "company": {
            "name": company.name,
            "company_id": company.company_id,
            "data": company.data,
        },
        "entities": [
            json.loads(
                entity.model_dump_json(
                    exclude={
                        "id",
                        "tenant_id",
                        "created_at",
                        "updated_at",
                        "is_deleted",
                        "meta_data",
                        "user_permissions",
                        "group_permissions",
                        "public_permission",
                    },
                    exclude_none=True,
                )
            )
            for entity in entities
        ],
        "artifacts": [
            {
                "artifact": json.loads(
                    artifact_with_chunks.artifact.model_dump_json(
                        exclude={
                            "id",
                            "tenant_id",
                            "created_at",
                            "updated_at",
                            "is_deleted",
                            "meta_data",
                            "user_permissions",
                            "group_permissions",
                            "public_permission",
                        },
                        exclude_none=True,
                    )
                ),
                "chunks": [
                    json.loads(
                        chunk.model_dump_json(
                            exclude={
                                "id",
                                "tenant_id",
                                "created_at",
                                "updated_at",
                                "is_deleted",
                                "meta_data",
                                "user_permissions",
                                "group_permissions",
                                "public_permission",
                                "embedding",
                            },
                            exclude_none=True,
                        )
                    )
                    for chunk in artifact_with_chunks.chunks
                ],
            }
            for artifact_with_chunks in artifacts_with_chunks
        ],
    }

    intro.append(json.dumps(result_data, ensure_ascii=False, indent=2))
    return "\n".join(intro) if intro else None


async def retrieve_related_artifacts_data(
    company: Company, payload: RetrieveRequest
) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""
    if not payload.text:
        return RetrieveResponse(
            tenant_id=company.id,
            company_id=company.company_id,
            entities=[],
            relations=[],
            chunks=[],
            text=None,
        )

    settings = Settings()

    # Step 1: Get company context from retrieve_type_only
    company_context_response = retrieve_type_only(company, payload)
    company_context = company_context_response.context or ""

    # Step 2: Extract entities from user question using LLM
    extracted_entities = await _extract_entities_from_text(
        payload.text, company_context, settings
    )

    # Step 3: Find matching entities in database
    found_entities, entity_ids = await _find_entities_from_extracted(
        company, extracted_entities
    )

    # Step 4: Generate embedding for user question
    query_embedding = await generate_embedding(payload.text, settings=settings)

    # Step 5: Perform hybrid search on artifact chunks
    artifacts_with_chunks = await _search_artifact_chunks(
        company, payload.text, query_embedding, entity_ids if entity_ids else None
    )

    # Step 6: Build JSON output text
    result_text = _build_result_json(company, found_entities, artifacts_with_chunks)

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=found_entities,
        relations=[],
        artifacts=artifacts_with_chunks,
        context=result_text,
    )


async def _check_content_sufficiency(
    user_question: str,
    retrieved_content: str,
    settings: Settings | None = None,
) -> bool:
    """Check if retrieved content is sufficient to answer the user's question."""
    if settings is None:
        settings = Settings()

    try:
        prompt_service = PromptService(settings)
        prompt_config = await prompt_service.get_prompt("content_sufficiency_check")
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_config["system"]),
            ("human", prompt_config["user"]),
        ])

        messages = prompt.format_messages(
            user_question=user_question, retrieved_content=retrieved_content
        )
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from LLM for content sufficiency check")
            return False

        result = content.strip().lower()
        is_sufficient = result.startswith("yes") or result == "yes"
        logger.debug("Content sufficiency check result: %s", is_sufficient)

    except Exception:
        logger.exception("Failed to check content sufficiency")
        return False

    return is_sufficient


async def retrieve_related_artifacts_text(
    company: Company, payload: RetrieveRequest
) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""
    if not payload.text:
        return RetrieveResponse(
            tenant_id=company.id,
            company_id=company.company_id,
            entities=[],
            relations=[],
            chunks=[],
            text=None,
        )

    settings = Settings()

    # Step 1: First call retrieve_related_artifacts_data
    initial_response = await retrieve_related_artifacts_data(company, payload)

    # Step 2: Check if content is sufficient
    retrieved_text = initial_response.context or ""
    is_sufficient = await _check_content_sufficiency(
        payload.text, retrieved_text, settings
    )

    # Step 3: If sufficient, return initial response
    if is_sufficient:
        return initial_response

    # Step 4: If not sufficient, load all artifacts and their text
    logger.info(
        "Content insufficient, loading all artifacts for company %s", company.id
    )
    all_artifacts = await Artifact.find_many(
        tenant_id=company.id, is_deleted=False, limit=10000
    )

    artifacts_with_chunks: list[ArtifactWithChunks] = []
    all_chunks: list[ArtifactChunk] = []
    artifact_texts: list[str] = []

    for artifact in all_artifacts:
        # Get text from chunks
        artifact_text = await artifact.get_text()
        if artifact_text:
            artifact_texts.append(f"Artifact {artifact.id}:\n{artifact_text}")

        # Get all chunks for this artifact
        chunks = await ArtifactChunk.find_many(
            artifact_id=artifact.id, is_deleted=False, limit=10000
        )
        all_chunks.extend(chunks)

        artifacts_with_chunks.append(
            ArtifactWithChunks(artifact=artifact, chunks=chunks)
        )

    # Build text response with all artifact texts
    intro = build_introduction(company)
    intro.append("\n\nتمام محتوای artifactها:\n\n")  # noqa: RUF001
    intro.append("\n\n---\n\n".join(artifact_texts))

    # Also include the initial response data
    if initial_response.context:
        intro.append("\n\n---\n\nاطلاعات اولیه:\n\n")  # noqa: RUF001
        intro.append(initial_response.context)

    result_text = "\n".join(intro)

    return RetrieveResponse(
        tenant_id=company.id,
        company_id=company.company_id,
        entities=initial_response.entities,
        relations=initial_response.relations,
        artifacts=artifacts_with_chunks,
        context=result_text,
    )


def _determine_resolution(payload: RetrieveRequest) -> RetrieveResolution:
    """Determine resolution based on payload if not already set."""
    if payload.resolution:
        return payload.resolution
    if payload.text:
        return RetrieveResolution.RELATED_ARTIFACTS_DATA
    if payload.entity_ids:
        return RetrieveResolution.SELECTED_ENTITIES_AND_MUTUAL_RELATIONS
    return RetrieveResolution.MAJOR_TYPE_AND_NAME


async def _execute_retrieval(
    company: Company, payload: RetrieveRequest
) -> RetrieveResponse:
    """Execute retrieval based on resolution type."""
    match payload.resolution:
        case RetrieveResolution.TYPE_ONLY:
            return retrieve_type_only(company, payload)
        case RetrieveResolution.MAJOR_TYPE_AND_NAME:
            return await retrieve_major_type_and_name(company, payload)
        case RetrieveResolution.SELECTED_ENTITIES:
            return await retrieve_selected_entities(company, payload)
        case RetrieveResolution.SELECTED_ENTITIES_AND_MUTUAL_RELATIONS:
            return await retrieve_selected_entities_and_mutual_relations(
                company, payload
            )
        case RetrieveResolution.RELATED_ARTIFACTS_DATA:
            return await retrieve_related_artifacts_data(company, payload)
        case RetrieveResolution.RELATED_ARTIFACTS_TEXT:
            return await retrieve_related_artifacts_text(company, payload)


async def retrieval(payload: RetrieveRequest) -> RetrieveResponse:
    """Retrieve entities and relations based on the request."""

    # Get tenant config to understand company structure
    company = await Company.get_by_id(
        id=payload.tenant_id, company_id=payload.company_id
    )
    if not company:
        raise BaseHTTPException(status_code=404, detail="Company not found")

    payload.resolution = _determine_resolution(payload)
    return await _execute_retrieval(company, payload)
