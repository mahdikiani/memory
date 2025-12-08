"""Safe query executor for SurrealDB with parameterized queries."""

import logging
import time
from typing import TYPE_CHECKING

from .query_builder import QueryBuilder

if TYPE_CHECKING:
    from .specialized_builders import (
        CombinedQueryBuilder,
        FullTextQueryBuilder,
        GraphQueryBuilder,
        VectorQueryBuilder,
    )

logger = logging.getLogger(__name__)


async def execute_query(
    query: str, variables: dict[str, object] | None = None
) -> list[dict[str, object]]:
    """
    Execute a parameterized SurrealDB query safely with performance monitoring.

    Args:
        query: SQL query with $param placeholders
        variables: Dictionary of parameters to bind

    Returns:
        List of result rows

    Examples:
        Simple query with parameters:
        ```python
        results = await execute_query(
            "SELECT * FROM user WHERE tenant_id = $tenant_id AND name = $name",
            {"tenant_id": "tenant_123", "name": "John"}
        )
        ```

        Query without parameters:
        ```python
        results = await execute_query("SELECT * FROM user WHERE is_deleted = false")
        ```

        Query with array parameter:
        ```python
        results = await execute_query(
            "SELECT * FROM user WHERE id IN $ids",
            {"ids": ["id1", "id2", "id3"]}
        )
        ```

    """
    from server.db import db_manager

    db = db_manager.get_db()
    start_time = time.perf_counter()
    query_type = _detect_query_type(query)

    try:
        # Try different ways SurrealDB Python SDK might accept parameters
        # Method 1: Try as keyword argument
        if variables:
            try:
                result = await db.query(query, variables=variables)
            except TypeError:
                # Method 2: Try as second positional argument
                try:
                    result = await db.query(query, variables)
                except TypeError:
                    # Method 3: Try using bind method if available
                    def raise_binding_error() -> None:
                        """Raise error for missing parameter binding."""
                        raise TypeError("No parameter binding method found")

                    try:
                        if hasattr(db, "bind"):
                            result = await db.query(query).bind(variables)
                        else:
                            raise_binding_error()
                    except (TypeError, AttributeError):
                        # Fallback: log warning and execute without parameters
                        # This should not happen if query_builder is used correctly
                        logger.exception(
                            "SurrealDB SDK does not support parameter binding. "
                            "Query may be vulnerable if variables are not properly "
                            "validated. Query: %s",
                            query[:100],
                        )
                        result = await db.query(query)
        else:
            result = await db.query(query)

        execution_time = time.perf_counter() - start_time
        rows_count = 0

        if result and len(result) > 0:
            rows = result[0].get("result", [])
            rows_count = len(rows)

            # Log performance metrics
            logger.debug(
                "Query executed successfully: type=%s, time=%.3fs, rows=%d, "
                "query_length=%d",
                query_type,
                execution_time,
                rows_count,
                len(query),
            )

            # Warn for slow queries (>1 second)
            if execution_time > 1.0:
                logger.warning(
                    "Slow query detected: type=%s, time=%.3fs, rows=%d, query=%s",
                    query_type,
                    execution_time,
                    rows_count,
                    query[:200],
                )

            return rows

        else:
            execution_time = time.perf_counter() - start_time
            logger.debug(
                "Query executed (no results): type=%s, time=%.3fs",
                query_type,
                execution_time,
            )
            return []
    except Exception:
        execution_time = time.perf_counter() - start_time
        logger.exception(
            "Query execution failed: type=%s, time=%.3fs, query=%s",
            query_type,
            execution_time,
            query[:200],
        )
        raise


def _detect_query_type(query: str) -> str:
    """
    Detect query type from query string.

    Args:
        query: SQL query string

    Returns:
        Query type identifier

    """
    query_upper = query.upper()
    if "COSINE_SIMILARITY" in query_upper or "SIMILARITY_SCORE" in query_upper:
        return "vector"
    if "@@" in query or "SEARCH::SCORE" in query_upper:
        return "fulltext"
    if "->" in query or "DISTANCE" in query_upper:
        return "graph"
    if "UNION ALL" in query_upper:
        return "combined"
    return "exact_match"


async def execute_exact_match_query(
    table: str,
    filters: dict[str, object],
    tenant_id: str,
    limit: int,
) -> list[dict[str, object]]:
    """
    Execute an exact match query safely.

    Args:
        table: Table name (must be whitelisted)
        filters: Filter dictionary
        tenant_id: Tenant ID
        limit: Result limit

    Returns:
        List of result rows

    """
    # Use ORM-like query builder for safe query construction
    query_builder = (
        QueryBuilder(table)
        .where("tenant_id", tenant_id)
        .where("is_deleted", False)
        .limit(limit)
    )

    # Add filters
    for field, value in filters.items():
        if isinstance(value, list):
            query_builder.where_in(field, value)
        else:
            query_builder.where(field, value)

    query, params = query_builder.build()
    return await execute_query(query, params)


async def execute_fulltext_query(
    query_text: str,
    filters: dict[str, object] | None,
    tenant_id: str,
    limit: int,
) -> list[dict[str, object]]:
    """
    Execute a fulltext search query safely.

    Args:
        query_text: Text to search for
        filters: Optional filters
        tenant_id: Tenant ID
        limit: Result limit

    Returns:
        List of result rows with relevance_score

    """
    query_builder = (
        FullTextQueryBuilder()
        .search(query_text)
        .where("tenant_id", tenant_id)
        .where("is_deleted", False)
        .limit(limit)
    )

    # Add filters
    if filters:
        for field, value in filters.items():
            if isinstance(value, list):
                query_builder.where_in(field, value)
            else:
                query_builder.where(field, value)

    query, params = query_builder.build()
    return await execute_query(query, params)


async def execute_vector_query(
    query_embedding: list[float],
    filters: dict[str, object] | None,
    tenant_id: str,
    limit: int,
) -> list[dict[str, object]]:
    """
    Execute a vector search query safely.

    Args:
        query_embedding: Query embedding vector
        filters: Optional filters
        tenant_id: Tenant ID
        limit: Result limit

    Returns:
        List of result rows with similarity_score

    """
    query_builder = (
        VectorQueryBuilder()
        .with_embedding_similarity(query_embedding)
        .where("tenant_id", tenant_id)
        .where("is_deleted", False)
        .where_is_not_none("embedding")
        .limit(limit)
    )

    # Add filters
    if filters:
        for field, value in filters.items():
            if isinstance(value, list):
                query_builder.where_in(field, value)
            else:
                query_builder.where(field, value)

    query, params = query_builder.build()
    return await execute_query(query, params)


async def execute_graph_query(
    tenant_id: str,
    entity_ids: list[str],
    relation_type: str | None,
    limit: int,
    min_depth: int = 1,
    max_depth: int = 1,
    order_by_distance: bool = False,
) -> list[dict[str, object]]:
    """
    Execute a graph traversal query safely with distance calculation.

    Args:
        tenant_id: Tenant ID
        entity_ids: List of starting entity IDs
        relation_type: Optional relation type filter
        limit: Result limit
        min_depth: Minimum traversal depth (default: 1)
        max_depth: Maximum traversal depth (default: 1)
        order_by_distance: Order results by distance (default: False)

    Returns:
        List of entity rows with distance field

    Examples:
        Find entities connected to 3 entities with distance between 3 and 7:
        ```python
        results = await execute_graph_query(
            tenant_id="tenant_123",
            entity_ids=["entity:1", "entity:2", "entity:3"],
            relation_type=None,
            limit=20,
            min_depth=3,
            max_depth=7,
            order_by_distance=True
        )
        # Results are ordered by distance (ascending) and include 'distance' field
        # Each result has: {..., "distance": 3, ...} or {..., "distance": 4, ...}, etc.
        ```

        Simple traversal with single depth:
        ```python
        results = await execute_graph_query(
            tenant_id="tenant_123",
            entity_ids=["entity:1"],
            relation_type="works_with",
            limit=10,
            min_depth=1,
            max_depth=2
        )
        ```

    """

    # Validate entity_ids
    validated_ids = []
    for entity_id in entity_ids[:20]:  # Limit to 20 entities
        if not isinstance(entity_id, str):
            continue
        # Basic validation - should not contain SQL keywords
        if any(
            keyword in entity_id.upper()
            for keyword in ["SELECT", "DROP", "DELETE", "INSERT", "UPDATE"]
        ):
            logger.warning("Suspicious entity_id detected: %s", entity_id)
            continue
        validated_ids.append(entity_id)

    if not validated_ids:
        logger.warning("No valid entity IDs provided for graph query")
        return []

    # Build query using GraphQueryBuilder
    query_builder = (
        GraphQueryBuilder()
        .from_entities(validated_ids)
        .depth_range(min_depth, max_depth)
        .where("tenant_id", tenant_id)
        .where("is_deleted", False)
        .limit(limit)
    )

    # Add relation_type filter
    if relation_type:
        query_builder.where("relation_type", relation_type)

    # Order by distance if requested
    if order_by_distance:
        query_builder.order_by_distance()

    query_sql, params = query_builder.build()

    return await execute_query(query_sql, params)


async def execute_combined_query(
    tenant_id: str,
    table: str | None = None,
    exact_match_filters: dict[str, object] | None = None,
    fulltext_query: str | None = None,
    vector_embedding: list[float] | None = None,
    graph_entity_ids: list[str] | None = None,
    graph_min_depth: int = 1,
    graph_max_depth: int = 1,
    graph_relation_type: str | None = None,
    graph_order_by_distance: bool = False,
    limit: int = 20,
) -> dict[str, list[dict[str, object]]]:
    """
    Execute combined query (Exact Match + Fulltext + Vector + Graph).

    Args:
        tenant_id: Tenant ID
        table: Table name (auto-detected if None)
        exact_match_filters: Exact match filters
        fulltext_query: Fulltext search query text
        vector_embedding: Vector embedding for similarity search
        graph_entity_ids: Entity IDs for graph search
        graph_min_depth: Minimum graph traversal depth
        graph_max_depth: Maximum graph traversal depth
        graph_relation_type: Graph relation type filter
        graph_order_by_distance: Order graph results by distance
        limit: Result limit for each query type

    Returns:
        Dictionary with 'main' (combined) and optionally 'graph' results

    Examples:
        Combined search with all types:
        ```python
        results = await execute_combined_query(
            tenant_id="tenant_123",
            exact_match_filters={"source_type": "document"},
            fulltext_query="search text",
            vector_embedding=[0.1, 0.2, 0.3],
            graph_entity_ids=["entity:1", "entity:2"],
            graph_min_depth=3,
            graph_max_depth=7,
            limit=20
        )
        # results = {
        #     "main": [...],  # Combined exact + fulltext + vector results
        #     "graph": [...]  # Graph search results
        # }
        ```

    """
    # Build combined query
    query_builder = CombinedQueryBuilder(table)

    # Add tenant and deleted filters
    query_builder.where_eq("tenant_id", tenant_id).where_eq("is_deleted", False)

    # Add exact match filters
    if exact_match_filters:
        for field, value in exact_match_filters.items():
            if isinstance(value, list):
                query_builder.where_in(field, value)
            else:
                query_builder.where_eq(field, value)

    # Add fulltext search
    if fulltext_query:
        query_builder.with_fulltext_search(fulltext_query)

    # Add vector search
    if vector_embedding:
        query_builder.with_vector_similarity(vector_embedding)

    # Add graph search
    if graph_entity_ids:
        query_builder.with_graph_search(
            entity_ids=graph_entity_ids,
            min_depth=graph_min_depth,
            max_depth=graph_max_depth,
            relation_type=graph_relation_type,
            order_by_distance=graph_order_by_distance,
            tenant_id=tenant_id,
        )

    # Set limit
    query_builder.limit(limit)

    # Build all queries
    queries = query_builder.build_all()

    # Execute queries
    results: dict[str, list[dict[str, object]]] = {}

    # Execute main query (combined)
    main_query, main_params = queries["main"]
    results["main"] = await execute_query(main_query, main_params)

    # Execute graph query if exists
    if "graph" in queries:
        graph_query, graph_params = queries["graph"]
        # Graph query already has tenant_id and is_deleted filters
        graph_results = await execute_query(graph_query, graph_params)
        results["graph"] = graph_results

    return results
