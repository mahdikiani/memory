"""Specialized query builders for vector, fulltext, and graph queries."""

from typing import Self

from .field_validation import sanitize_field_name
from .metadata import (
    _get_fulltext_field,
    _get_graph_edge_model,
    _get_graph_node_model,
    _get_table_name,
    _get_vector_field,
)
from .models import BaseSurrealEntity
from .query_builder import QueryBuilder
from .utils import get_all_subclasses


class VectorQueryBuilder(QueryBuilder):
    """Specialized query builder for vector similarity search."""

    def __init__(self, table: str | None = None) -> None:
        """
        Initialize vector query builder.

        Args:
            table: Table name (auto-detected from model with vector field if None)

        """
        if table is None:
            # Dynamically find model with vector field from metadata

            model_classes = get_all_subclasses(BaseSurrealEntity)
            for model_class in model_classes:
                vector_field = _get_vector_field(model_class)
                if vector_field:
                    table = _get_table_name(model_class)
                    break
            else:
                raise ValueError(
                    "No model with 'surreal_vector_field' metadata found. "
                    "Please specify table name explicitly or add "
                    "'surreal_vector_field: True' to field json_schema_extra."
                )

        super().__init__(table)
        self._embedding_param: str | None = None

    def with_embedding_similarity(self, query_embedding: list[float]) -> Self:
        """
        Add vector similarity calculation.

        Args:
            query_embedding: Query embedding vector

        Returns:
            Self for method chaining

        """
        self._embedding_param = self._add_param(query_embedding)
        return self

    def build(self) -> tuple[str, dict[str, object]]:
        """
        Build vector similarity query.

        Returns:
            Tuple of (query string, parameters dict)

        """
        # Build WHERE clause
        where_clause = ""
        if self._where_parts:
            where_clause = " WHERE " + " AND ".join(self._where_parts)

        # Build ORDER BY clause
        order_by_clause = ""
        if self._order_by:
            order_by_clause = " ORDER BY " + ", ".join(self._order_by)
        elif self._embedding_param:
            order_by_clause = " ORDER BY similarity_score DESC"

        # Build LIMIT clause
        limit_clause = ""
        if self._limit_value is not None:
            limit_param = self._add_param(self._limit_value)
            limit_clause = " LIMIT " + limit_param

        # Build query safely without f-string interpolation
        if self._embedding_param:
            query_parts = [
                "SELECT",
                "*,",
                "vector::similarity::cosine(embedding,",
                self._embedding_param,
                ")",
                "AS",
                "similarity_score",
                "FROM",
                self.table,
            ]
        else:
            select_clause = ", ".join(self._select_fields)
            query_parts = ["SELECT", select_clause, "FROM", self.table]

        if where_clause:
            query_parts.append(where_clause)
        if order_by_clause:
            query_parts.append(order_by_clause)
        if limit_clause:
            query_parts.append(limit_clause)

        query = " ".join(query_parts)

        return query, self._params


class FullTextQueryBuilder(QueryBuilder):
    """Specialized query builder for fulltext search."""

    def __init__(self, table: str | None = None) -> None:
        """
        Initialize fulltext query builder.

        Args:
            table: Table name (auto-detected from model with fulltext field if None)

        """
        if table is None:
            # Dynamically find model with fulltext field from metadata
            model_classes = get_all_subclasses(BaseSurrealEntity)
            for model_class in model_classes:
                fulltext_field = _get_fulltext_field(model_class)
                if fulltext_field:
                    table = _get_table_name(model_class)
                    break
            else:
                raise ValueError(
                    "No model with 'surreal_fulltext_field' metadata found. "
                    "Please specify table name explicitly or add "
                    "'surreal_fulltext_field: True' to field json_schema_extra."
                )

        super().__init__(table)
        self._query_text_param: str | None = None

    def search(self, query_text: str) -> Self:
        """
        Add fulltext search condition.

        Args:
            query_text: Text to search for

        Returns:
            Self for method chaining

        """
        self._query_text_param = self._add_param(query_text)
        return self

    def build(self) -> tuple[str, dict[str, object]]:
        """
        Build fulltext search query.

        Returns:
            Tuple of (query string, parameters dict)

        """
        # Add fulltext search condition
        if self._query_text_param:
            # Get fulltext field name from metadata
            model_classes = get_all_subclasses(BaseSurrealEntity)
            for model_class in model_classes:
                fulltext_field = _get_fulltext_field(model_class)
                if fulltext_field:
                    text_field = sanitize_field_name(fulltext_field)
                    self._where_parts.insert(
                        0, f"{text_field} @@ {self._query_text_param}"
                    )
                    break

        # Build WHERE clause
        where_clause = ""
        if self._where_parts:
            where_clause = " WHERE " + " AND ".join(self._where_parts)

        # Build ORDER BY clause
        order_by_clause = ""
        if self._order_by:
            order_by_clause = " ORDER BY " + ", ".join(self._order_by)
        else:
            order_by_clause = " ORDER BY relevance_score DESC"

        # Build LIMIT clause
        limit_clause = ""
        if self._limit_value is not None:
            limit_param = self._add_param(self._limit_value)
            limit_clause = " LIMIT " + limit_param

        # Build query safely without f-string interpolation
        query_parts = [
            "SELECT",
            "*,",
            "search::score(0)",
            "AS",
            "relevance_score",
            "FROM",
            self.table,
        ]
        if where_clause:
            query_parts.append(where_clause)
        if order_by_clause:
            query_parts.append(order_by_clause)
        if limit_clause:
            query_parts.append(limit_clause)

        query = " ".join(query_parts)

        return query, self._params


class GraphQueryBuilder(QueryBuilder):
    """Specialized query builder for graph path traversal queries."""

    def __init__(
        self,
        node_table: str | None = None,
        edge_table: str | None = None,
    ) -> None:
        """
        Initialize graph query builder.

        Args:
            node_table: Node table name (auto-detected if None)
            edge_table: Edge table name (auto-detected if None)

        """
        # Auto-detect node and edge tables from metadata
        if node_table is None:
            node_model = _get_graph_node_model()
            if node_model:
                node_table = _get_table_name(node_model)
            else:
                raise ValueError(
                    "No model with 'surreal_graph_node' metadata found. "
                    "Please specify node_table explicitly."
                )

        if edge_table is None:
            edge_model = _get_graph_edge_model()
            if edge_model:
                edge_table = _get_table_name(edge_model)
            else:
                raise ValueError(
                    "No model with 'surreal_graph_edge' metadata found. "
                    "Please specify edge_table explicitly."
                )

        # Initialize with node_table (for QueryBuilder)
        super().__init__(node_table)
        self.node_table = node_table
        self.edge_table = edge_table
        self._from_entity_ids: list[str] = []
        self._to_entity_ids: list[str] | None = None
        self._min_depth: int = 1
        self._max_depth: int = 1
        self._order_by_distance: bool = False

    def from_entities(self, entity_ids: list[str]) -> Self:
        """
        Set starting entity IDs for traversal.

        Args:
            entity_ids: List of starting entity IDs

        Returns:
            Self for method chaining

        """
        self._from_entity_ids = entity_ids
        return self

    def to_entities(self, entity_ids: list[str]) -> Self:
        """
        Set target entity IDs for traversal (optional).

        Args:
            entity_ids: List of target entity IDs

        Returns:
            Self for method chaining

        """
        self._to_entity_ids = entity_ids
        return self

    def min_depth(self, depth: int) -> Self:
        """
        Set minimum traversal depth.

        Args:
            depth: Minimum depth (1-10)

        Returns:
            Self for method chaining

        """
        if not isinstance(depth, int) or depth < 1 or depth > 10:
            raise ValueError("Depth must be an integer between 1 and 10")
        self._min_depth = depth
        return self

    def max_depth(self, depth: int) -> Self:
        """
        Set maximum traversal depth.

        Args:
            depth: Maximum depth (1-10)

        Returns:
            Self for method chaining

        """
        if not isinstance(depth, int) or depth < 1 or depth > 10:
            raise ValueError("Depth must be an integer between 1 and 10")
        self._max_depth = depth
        return self

    def depth_range(self, min_depth: int, max_depth: int) -> Self:
        """
        Set depth range for traversal.

        Args:
            min_depth: Minimum depth (1-10)
            max_depth: Maximum depth (1-10)

        Returns:
            Self for method chaining

        """
        if not isinstance(min_depth, int) or min_depth < 1 or min_depth > 10:
            raise ValueError("min_depth must be an integer between 1 and 10")
        if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
            raise ValueError("max_depth must be an integer between 1 and 10")
        if min_depth > max_depth:
            raise ValueError("min_depth must be <= max_depth")
        self._min_depth = min_depth
        self._max_depth = max_depth
        return self

    def order_by_distance(self) -> Self:
        """
        Order results by distance (ascending - closest first).

        Returns:
            Self for method chaining

        """
        self._order_by_distance = True
        return self

    def limit(self, count: int) -> Self:
        """
        Set result limit.

        Args:
            count: Maximum number of results

        Returns:
            Self for method chaining

        """
        if not isinstance(count, int) or count < 0:
            raise ValueError("Limit must be a non-negative integer")
        self._limit_value = count
        return self

    def where(self, field: str, value: object, operator: str = "=") -> Self:
        """
        Add WHERE condition to edge filter.

        Args:
            field: Field name
            value: Value to compare
            operator: Comparison operator

        Returns:
            Self for method chaining

        """
        # Use parent's where method
        return super().where(field, value, operator)

    def build(self) -> tuple[str, dict[str, object]]:
        """
        Build graph traversal query with distance calculation.

        Returns:
            Tuple of (query string, parameters dict)

        Examples:
            Simple traversal with single depth:
            ```python
            query_builder = GraphQueryBuilder() \
                .from_entities(["entity:1", "entity:2"]) \
                .max_depth(3) \
                .where("tenant_id", "tenant_123") \
                .limit(20)
            query_sql, params = query_builder.build()
            ```

            Traversal with depth range and distance ordering:
            ```python
            query_builder = GraphQueryBuilder() \
                .from_entities(["entity:1", "entity:2", "entity:3"]) \
                .depth_range(min_depth=3, max_depth=7) \
                .where("tenant_id", "tenant_123") \
                .where("is_deleted", False) \
                .order_by_distance() \
                .limit(20)
            query_sql, params = query_builder.build()
            # Results include 'distance' field and are ordered by distance (ascending)
            ```

            Generated SQL for depth_range(3, 7):
            ```sql
            SELECT *, 3 AS distance FROM entity
            WHERE id IN [$param_0, $param_1, $param_2]
            ->->-> relation WHERE tenant_id = $param_3 AND is_deleted = $param_4
            UNION ALL
            SELECT *, 4 AS distance FROM entity
            WHERE id IN [$param_0, $param_1, $param_2]
            ->->->-> relation WHERE tenant_id = $param_3 AND is_deleted = $param_4
            UNION ALL
            SELECT *, 5 AS distance FROM entity
            WHERE id IN [$param_0, $param_1, $param_2]
            ->->->->-> relation WHERE tenant_id = $param_3 AND is_deleted = $param_4
            UNION ALL
            SELECT *, 6 AS distance FROM entity
            WHERE id IN [$param_0, $param_1, $param_2]
            ->->->->->-> relation WHERE tenant_id = $param_3 AND is_deleted = $param_4
            UNION ALL
            SELECT *, 7 AS distance FROM entity
            WHERE id IN [$param_0, $param_1, $param_2]
            ->->->->->->-> relation WHERE tenant_id = $param_3 AND is_deleted = $param_4
            ORDER BY distance ASC
            LIMIT $param_5
            ```

        """
        if not self._from_entity_ids:
            raise ValueError("At least one starting entity ID is required")

        if self._min_depth > self._max_depth:
            raise ValueError("min_depth must be <= max_depth")

        # Build FROM clause with entity IDs
        from_params = [self._add_param(eid) for eid in self._from_entity_ids]
        from_list = ", ".join(from_params)

        # Build WHERE clause for edges
        where_clause = ""
        if self._where_parts:
            where_clause = " WHERE " + " AND ".join(self._where_parts)

        # Add target entity filter if specified
        if self._to_entity_ids:
            to_params = [self._add_param(eid) for eid in self._to_entity_ids]
            to_list = ", ".join(to_params)
            if where_clause:
                where_clause += f" AND id IN [{to_list}]"
            else:
                where_clause = f" WHERE id IN [{to_list}]"

        # Build queries for each depth level
        depth_queries: list[str] = []
        for depth in range(self._min_depth, self._max_depth + 1):
            # Build path traversal: ->->->-> (depth times)
            path_traversal = "->" * depth

            # Build SELECT with distance
            query_parts = [
                "SELECT",
                "*,",
                str(depth),
                "AS",
                "distance",
                "FROM",
                self.node_table,
                "WHERE",
                "id",
                "IN",
                "[" + from_list + "]",
                path_traversal,
                self.edge_table,
            ]

            if where_clause:
                query_parts.append(where_clause)

            depth_queries.append(" ".join(query_parts))

        # Combine queries with UNION ALL
        if len(depth_queries) == 1:
            # Single depth - no need for UNION
            query = depth_queries[0]
        else:
            # Multiple depths - use UNION ALL
            query = " UNION ALL ".join(depth_queries)

        # Add ORDER BY distance if requested
        if self._order_by_distance:
            query += " ORDER BY distance ASC"

        # Build LIMIT clause
        limit_param = self._add_param(self._limit_value)
        limit_clause = f" LIMIT {limit_param}"
        query += " " + limit_clause

        return query, self._params


class CombinedQueryBuilder(QueryBuilder):
    """
    Query builder that combines Exact Match + Fulltext + Vector search.

    Graph search is handled separately as it requires a different query structure.
    """

    def __init__(self, table: str | None = None) -> None:
        """
        Initialize combined query builder.

        Args:
            table: Table name (auto-detected from model with vector/fulltext
                field if None)

        """
        if table is None:
            # Try to find table with vector or fulltext field
            model_classes = get_all_subclasses(BaseSurrealEntity)
            for model_class in model_classes:
                vector_field = _get_vector_field(model_class)
                fulltext_field = _get_fulltext_field(model_class)
                if vector_field or fulltext_field:
                    table = _get_table_name(model_class)
                    break
            else:
                raise ValueError(
                    "No model with 'surreal_vector_field' or "
                    "'surreal_fulltext_field' metadata found. "
                    "Please specify table name explicitly."
                )

        super().__init__(table)

        # Vector search
        self._embedding_param: str | None = None
        self._use_vector: bool = False

        # Fulltext search
        self._query_text_param: str | None = None
        self._fulltext_field: str | None = None
        self._use_fulltext: bool = False

        # Graph search (separate)
        self._graph_query_builder: GraphQueryBuilder | None = None

    def with_fulltext_search(self, query_text: str) -> Self:
        """
        Add fulltext search condition.

        Args:
            query_text: Text to search for

        Returns:
            Self for method chaining

        """
        self._query_text_param = self._add_param(query_text)
        self._use_fulltext = True

        # Find fulltext field
        model_classes = get_all_subclasses(BaseSurrealEntity)
        for model_class in model_classes:
            fulltext_field = _get_fulltext_field(model_class)
            if fulltext_field:
                self._fulltext_field = sanitize_field_name(fulltext_field)
                break

        if not self._fulltext_field:
            raise ValueError(
                "No model with 'surreal_fulltext_field' metadata found. "
                "Cannot use fulltext search."
            )

        return self

    def with_vector_similarity(self, query_embedding: list[float]) -> Self:
        """
        Add vector similarity search.

        Args:
            query_embedding: Query embedding vector

        Returns:
            Self for method chaining

        """
        self._embedding_param = self._add_param(query_embedding)
        self._use_vector = True
        return self

    def with_graph_search(
        self,
        entity_ids: list[str],
        min_depth: int = 1,
        max_depth: int = 1,
        relation_type: str | None = None,
        order_by_distance: bool = False,
        tenant_id: str | None = None,
    ) -> Self:
        """
        Add graph search (will be executed separately).

        Args:
            entity_ids: List of starting entity IDs
            min_depth: Minimum traversal depth
            max_depth: Maximum traversal depth
            relation_type: Optional relation type filter
            order_by_distance: Order results by distance
            tenant_id: Tenant ID (will be added as filter)

        Returns:
            Self for method chaining

        """
        self._graph_query_builder = (
            GraphQueryBuilder()
            .from_entities(entity_ids)
            .depth_range(min_depth, max_depth)
        )

        # Add tenant and deleted filters if tenant_id provided
        if tenant_id:
            self._graph_query_builder.where("tenant_id", tenant_id)
            self._graph_query_builder.where("is_deleted", False)

        if relation_type:
            self._graph_query_builder.where("relation_type", relation_type)

        if order_by_distance:
            self._graph_query_builder.order_by_distance()

        return self

    def _add_vector_select(self, select_parts: list[str]) -> None:
        """Add vector similarity to SELECT clause."""
        if not self._embedding_param:
            raise ValueError(
                "Vector search requires embedding. Use with_vector_similarity()"
            )
        select_parts.append(
            f"cosine_similarity(embedding, {self._embedding_param}) AS similarity_score"
        )
        # Ensure embedding is not None
        self.where_is_not_none("embedding")

    def _add_fulltext_select(self, select_parts: list[str]) -> None:
        """Add fulltext score to SELECT clause."""
        if not self._query_text_param:
            raise ValueError(
                "Fulltext search requires query text. Use with_fulltext_search()"
            )
        select_parts.append("search::score(0) AS relevance_score")
        # Add fulltext condition
        self._where_parts.insert(
            0, f"{self._fulltext_field} @@ {self._query_text_param}"
        )

    def _build_select_clause(self) -> str:
        """Build SELECT clause with vector and fulltext scores."""
        select_parts = list(self._select_fields)

        if self._use_vector:
            self._add_vector_select(select_parts)

        if self._use_fulltext:
            self._add_fulltext_select(select_parts)

        return ", ".join(select_parts)

    def _build_where_clause(self) -> str:
        """Build WHERE clause."""
        if not self._where_parts:
            return ""
        return " WHERE " + " AND ".join(self._where_parts)

    def _build_order_by_clause(self) -> str:
        """Build ORDER BY clause."""
        if self._order_by:
            return " ORDER BY " + ", ".join(self._order_by)

        if self._use_vector and self._use_fulltext:
            return " ORDER BY similarity_score DESC, relevance_score DESC"

        if self._use_vector:
            return " ORDER BY similarity_score DESC"

        if self._use_fulltext:
            return " ORDER BY relevance_score DESC"

        return ""

    def _build_limit_clause(self) -> str:
        """Build LIMIT clause."""
        if self._limit_value is None:
            return ""
        limit_param = self._add_param(self._limit_value)
        return f" LIMIT {limit_param}"

    def build(self) -> tuple[str, dict[str, object]]:
        """
        Build combined query (Exact Match + Fulltext + Vector).

        Returns:
            Tuple of (query string, parameters dict)

        Examples:
            Combined search with all three types:
            ```python
            query_builder = CombinedQueryBuilder() \
                .where_eq("tenant_id", "tenant_123") \
                .where_eq("is_deleted", False) \
                .with_fulltext_search("search text") \
                .with_vector_similarity([0.1, 0.2, 0.3]) \
                .limit(20)
            query_sql, params = query_builder.build()
            ```

            Generated SQL:
            ```sql
            SELECT *,
                   cosine_similarity(embedding, $param_2) AS similarity_score,
                   search::score(0) AS relevance_score
            FROM knowledge_chunk
            WHERE tenant_id = $param_0
              AND is_deleted = $param_1
              AND text @@ $param_3
              AND embedding IS NOT NONE
            ORDER BY similarity_score DESC, relevance_score DESC
            LIMIT $param_4
            ```

        """
        select_clause = self._build_select_clause()
        where_clause = self._build_where_clause()
        order_by_clause = self._build_order_by_clause()
        limit_clause = self._build_limit_clause()

        # Build query
        query_parts = ["SELECT", select_clause, "FROM", self.table]

        if where_clause:
            query_parts.append(where_clause)
        if order_by_clause:
            query_parts.append(order_by_clause)
        if limit_clause:
            query_parts.append(limit_clause)

        query = " ".join(query_parts)

        return query, self._params

    def build_graph_query(self) -> tuple[str, dict[str, object]] | None:
        """
        Build graph search query (separate from main query).

        Returns:
            Tuple of (query string, parameters dict) or None if no graph search

        """
        if self._graph_query_builder is None:
            return None

        # Merge params from graph query builder
        graph_query, graph_params = self._graph_query_builder.build()

        # Update param names to avoid conflicts
        updated_params = {}
        for key, value in graph_params.items():
            new_key = f"graph_{key}"
            updated_params[new_key] = value
            graph_query = graph_query.replace(f"${key}", f"${new_key}")

        return graph_query, updated_params

    def build_all(self) -> dict[str, tuple[str, dict[str, object]]]:
        """
        Build all queries (main + graph if exists).

        Returns:
            Dictionary with 'main' and optionally 'graph' queries

        """
        result = {"main": self.build()}

        graph_query = self.build_graph_query()
        if graph_query:
            result["graph"] = graph_query

        return result
