"""Routes for retrieve endpoints."""

from fastapi import APIRouter

from ..utils.entity_service import get_entities
from ..utils.relation_service import get_relations
from .chain import classify_query, extract_filters
from .retrievers.hybrid_retriever import HybridRetriever
from .schemas import (
    ChunkResult,
    EntityResult,
    RagContext,
    RagRetrieveRequest,
    RagRetrieveResponse,
    RelationResult,
    RetrieveEntityResponse,
    RetrieveRequest,
)

router = APIRouter(tags=["retrieve"])


@router.post(
    "/retrieve/entity",
    response_model=RetrieveEntityResponse,
)
async def retrieve_entity(payload: RetrieveRequest) -> RetrieveEntityResponse:
    """Fetch entities and relations using exact/structured filters."""
    if payload.entity_ids:
        filters = {"id": payload.entity_ids}
    else:
        filters = {}
        if payload.entity_type:
            filters["entity_type"] = payload.entity_type
        if payload.name:
            filters["name"] = payload.name

    entities = await get_entities(
        tenant_id=payload.tenant_id,
        filters=filters or None,
        limit=payload.limit_entities,
    )

    relations = await get_relations(
        tenant_id=payload.tenant_id,
        entity_id=payload.related_entity_id,
        relation_type=payload.relation_type,
        limit=payload.limit_relations,
    )

    entity_results = [
        EntityResult(
            entity_id=e.id or "",
            entity_type=e.entity_type,
            name=e.name,
            attributes=e.attributes,
        )
        for e in entities
    ]

    relation_results = [
        RelationResult(
            relation_id=r.id or "",
            from_entity_id=r.from_entity_id,
            to_entity_id=r.to_entity_id,
            relation_type=r.relation_type,
            attributes=r.attributes,
        )
        for r in relations
    ]

    return RetrieveEntityResponse(
        tenant_id=payload.tenant_id,
        entities=entity_results,
        relations=relation_results,
    )


@router.post(
    "/retrieve",
    response_model=RagRetrieveResponse,
)
async def retrieve_rag(payload: RagRetrieveRequest) -> RagRetrieveResponse:
    """Run hybrid RAG retrieval (exact/fulltext/vector/graph) for a question."""
    query_type = payload.query_type
    if query_type is None:
        query_type = await classify_query(payload.question)

    filters = await extract_filters(payload.question, payload.hints)
    entity_ids = filters.get("entity_ids") if isinstance(filters, dict) else None

    hybrid = HybridRetriever(
        tenant_id=payload.tenant_id,
        use_exact_match=query_type in ("structured", "hybrid"),
        use_fulltext=True,
        use_vector=query_type in ("semantic", "hybrid"),
        use_graph=query_type in ("structured", "hybrid") and bool(entity_ids),
        exact_match_filters=filters if isinstance(filters, dict) else {},
        vector_filters=filters if isinstance(filters, dict) else {},
        entity_ids=entity_ids if isinstance(entity_ids, list) else None,
        relation_type=filters.get("relation_type")
        if isinstance(filters, dict)
        else None,  # type: ignore[arg-type]
        limit_per_type=payload.limits.get("max_chunks", 10),
    )

    documents = await hybrid._aget_relevant_documents(payload.question)

    # Split into structured chunks/entities/relations for the response
    chunks: list[dict[str, object]] = []
    entities: list[dict[str, object]] = []
    relations: list[dict[str, object]] = []

    for doc in documents:
        meta = doc.metadata or {}
        doc_type = meta.get("type")
        if doc_type == "chunk":
            chunks.append({
                "chunk_id": meta.get("chunk_id", ""),
                "source_id": meta.get("source_id", ""),
                "chunk_index": meta.get("chunk_index", 0),
                "score": meta.get("similarity_score")
                or meta.get("relevance_score")
                or 0.0,
                "text": doc.page_content,
            })
        elif doc_type == "entity":
            entities.append({
                "entity_id": meta.get("entity_id", ""),
                "entity_type": meta.get("entity_type", ""),
                "name": meta.get("name", ""),
                "attributes": meta.get("attributes", {}),
                "distance": meta.get("distance"),
            })
        elif doc_type == "relation":
            relations.append({
                "relation_id": meta.get("relation_id", ""),
                "from_entity_id": meta.get("from_entity_id", ""),
                "to_entity_id": meta.get("to_entity_id", ""),
                "relation_type": meta.get("relation_type", ""),
                "attributes": meta.get("attributes", {}),
                "distance": meta.get("distance"),
            })

    entity_results = [
        EntityResult(
            entity_id=e.get("entity_id", ""),
            entity_type=e.get("entity_type", ""),
            name=e.get("name", ""),
            attributes=e.get("attributes", {}),
            distance=e.get("distance"),
        )
        for e in entities[: payload.limits.get("max_entities", 20)]
    ]

    relation_results = [
        RelationResult(
            relation_id=r.get("relation_id", ""),
            from_entity_id=r.get("from_entity_id", ""),
            to_entity_id=r.get("to_entity_id", ""),
            relation_type=r.get("relation_type", ""),
            attributes=r.get("attributes", {}),
            distance=r.get("distance"),
        )
        for r in relations[: payload.limits.get("max_entities", 20)]
    ]

    chunk_results = [
        ChunkResult(
            chunk_id=c.get("chunk_id", ""),
            source_id=c.get("source_id", ""),
            chunk_index=int(c.get("chunk_index", 0) or 0),
            score=float(c.get("score", 0.0) or 0.0),
            text=c.get("text", ""),
        )
        for c in chunks[: payload.limits.get("max_chunks", 20)]
    ]

    context = RagContext(
        entities=entity_results,
        relations=relation_results,
        chunks=chunk_results,
    )

    return RagRetrieveResponse(
        tenant_id=payload.tenant_id,
        question=payload.question,
        query_type=query_type,
        filters=filters if isinstance(filters, dict) else None,
        context=context,
    )
