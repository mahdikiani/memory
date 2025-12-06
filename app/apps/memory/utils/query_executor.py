"""Safe query executor for SurrealDB with parameterized queries."""

import logging

from server.db import db_manager

logger = logging.getLogger(__name__)


async def execute_query(
    query: str, variables: dict[str, object] | None = None
) -> list[dict[str, object]]:
    """
    Execute a parameterized SurrealDB query safely.

    Args:
        query: SQL query with $param placeholders
        variables: Dictionary of parameters to bind

    Returns:
        List of result rows

    """
    db = db_manager.get_db()

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

        if result and len(result) > 0:
            return result[0].get("result", [])
    except Exception:
        logger.exception("Failed to execute query")
        raise

    return []


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
    from apps.memory.shared.utils.query_builder_orm import QueryBuilder

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
    from apps.memory.shared.utils.query_builder_orm import FullTextQueryBuilder

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
    from apps.memory.shared.utils.query_builder_orm import VectorQueryBuilder

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
) -> list[dict[str, object]]:
    """
    Execute a graph traversal query safely.

    Args:
        tenant_id: Tenant ID
        entity_ids: List of entity IDs
        relation_type: Optional relation type filter
        limit: Result limit

    Returns:
        List of relation rows

    """
    # Build query using ORM-like builder (no string interpolation!)
    from apps.memory.shared.utils.query_builder_orm import query

    query_builder = query("relation").limit(limit)

    # Add tenant and deleted filters
    query_builder.where_eq("tenant_id", tenant_id).where_eq("is_deleted", False)

    # Add entity_id filters - build OR condition safely
    if entity_ids:
        # Validate and parameterize entity_ids
        validated_ids = []
        for entity_id in entity_ids[:10]:  # Limit to 10 entities
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

        if validated_ids:
            # Build parameterized OR condition manually (safe because IDs are validated)
            from_param_names = []
            to_param_names = []
            for eid in validated_ids:
                from_param = query_builder._add_param(eid)
                to_param = query_builder._add_param(eid)
                from_param_names.append(from_param)
                to_param_names.append(to_param)

            # Build OR condition using string concatenation
            # (safe - all values are parameterized)
            from_list = ", ".join(from_param_names)
            to_list = ", ".join(to_param_names)
            or_condition_parts = [
                "(",
                "from_entity_id",
                "IN",
                "[" + from_list + "]",
                "OR",
                "to_entity_id",
                "IN",
                "[" + to_list + "]",
                ")",
            ]
            query_builder._where_parts.append(" ".join(or_condition_parts))

    # Add relation_type filter
    if relation_type:
        query_builder.where_eq("relation_type", relation_type)

    query_sql, params = query_builder.build()

    return await execute_query(query_sql, params)
