"""ORM-like query builder for SurrealDB to prevent SQL injection."""

import logging
from typing import Self

from .query_builder import (
    sanitize_field_name,
    validate_field_name,
)

logger = logging.getLogger(__name__)


class QueryBuilder:
    """ORM-like query builder for safe SurrealDB queries."""

    def __init__(self, table: str) -> None:
        """
        Initialize query builder.

        Args:
            table: Table name (must be whitelisted)

        """
        self._validate_table(table)
        self.table = table
        self._where_parts: list[str] = []
        self._params: dict[str, object] = {}
        self._param_counter = 0
        self._select_fields: list[str] = ["*"]
        self._order_by: list[str] = []
        self._limit_value: int | None = None

    @staticmethod
    def _validate_table(table: str) -> None:
        """Validate table name is safe."""
        allowed_tables = {
            "entity",
            "knowledge_source",
            "knowledge_chunk",
            "relation",
            "tenant_config",
            "ingest_job",
        }
        if table not in allowed_tables:
            raise ValueError(f"Unsafe table name: {table}")

    def _add_param(self, value: object) -> str:
        """
        Add a parameter and return its placeholder name.

        Args:
            value: Parameter value

        Returns:
            Parameter placeholder name (e.g., "$param_0")

        """
        param_name = f"param_{self._param_counter}"
        self._params[param_name] = value
        self._param_counter += 1
        return f"${param_name}"

    def where_eq(self, field: str, value: object) -> Self:
        """
        Add WHERE field = value condition.

        Args:
            field: Field name (must be validated)
            value: Value to compare

        Returns:
            Self for method chaining

        """
        return self.where(field, value, operator="=")

    def where(self, field: str, value: object, operator: str = "=") -> Self:
        """
        Add a WHERE condition.

        Args:
            field: Field name (must be validated)
            value: Value to compare
            operator: Comparison operator (=, !=, >, <, etc.)

        Returns:
            Self for method chaining

        """
        if not validate_field_name(field):
            raise ValueError(f"Unsafe field name: {field}")

        sanitized_field = sanitize_field_name(field)
        param_placeholder = self._add_param(value)

        allowed_operators = {"=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN"}
        if operator.upper() not in allowed_operators:
            raise ValueError(f"Unsafe operator: {operator}")

        if operator.upper() == "IN":
            if not isinstance(value, list):
                raise ValueError("IN operator requires a list value")
            param_placeholders = [self._add_param(v) for v in value]
            # Build IN clause safely without f-string interpolation
            in_list = ", ".join(param_placeholders)
            condition_parts = [sanitized_field, "IN", "[" + in_list + "]"]
            self._where_parts.append(" ".join(condition_parts))
        elif operator.upper() == "NOT IN":
            if not isinstance(value, list):
                raise ValueError("NOT IN operator requires a list value")
            param_placeholders = [self._add_param(v) for v in value]
            # Build NOT IN clause safely without f-string interpolation
            in_list = ", ".join(param_placeholders)
            condition_parts = [sanitized_field, "NOT", "IN", "[" + in_list + "]"]
            self._where_parts.append(" ".join(condition_parts))
        else:
            # Build condition safely without f-string interpolation
            condition_parts = [sanitized_field, operator, param_placeholder]
            self._where_parts.append(" ".join(condition_parts))

        return self

    def where_in(self, field: str, values: list[object]) -> Self:
        """
        Add WHERE IN condition.

        Args:
            field: Field name
            values: List of values

        Returns:
            Self for method chaining

        """
        return self.where(field, values, operator="IN")

    def where_not_in(self, field: str, values: list[object]) -> Self:
        """
        Add WHERE NOT IN condition.

        Args:
            field: Field name
            values: List of values

        Returns:
            Self for method chaining

        """
        return self.where(field, values, operator="NOT IN")

    def where_is_none(self, field: str) -> Self:
        """
        Add WHERE IS NONE condition.

        Args:
            field: Field name

        Returns:
            Self for method chaining

        """
        if not validate_field_name(field):
            raise ValueError(f"Unsafe field name: {field}")
        sanitized_field = sanitize_field_name(field)
        self._where_parts.append(f"{sanitized_field} IS NONE")
        return self

    def where_is_not_none(self, field: str) -> "QueryBuilder":
        """
        Add WHERE IS NOT NONE condition.

        Args:
            field: Field name

        Returns:
            Self for method chaining

        """
        if not validate_field_name(field):
            raise ValueError(f"Unsafe field name: {field}")
        sanitized_field = sanitize_field_name(field)
        self._where_parts.append(f"{sanitized_field} IS NOT NONE")
        return self

    def select(self, *fields: str) -> Self:
        """
        Specify fields to select.

        Args:
            *fields: Field names to select

        Returns:
            Self for method chaining

        """
        validated_fields = []
        for field in fields:
            if not validate_field_name(field):
                raise ValueError(f"Unsafe field name: {field}")
            validated_fields.append(sanitize_field_name(field))
        self._select_fields = validated_fields if validated_fields else ["*"]
        return self

    def order_by(self, field: str, direction: str = "ASC") -> Self:
        """
        Add ORDER BY clause.

        Args:
            field: Field name to order by
            direction: ASC or DESC

        Returns:
            Self for method chaining

        """
        if not validate_field_name(field):
            raise ValueError(f"Unsafe field name: {field}")
        if direction.upper() not in {"ASC", "DESC"}:
            raise ValueError(f"Invalid direction: {direction}")

        sanitized_field = sanitize_field_name(field)
        self._order_by.append(f"{sanitized_field} {direction.upper()}")
        return self

    def limit(self, count: int) -> "QueryBuilder":
        """
        Add LIMIT clause.

        Args:
            count: Maximum number of results

        Returns:
            Self for method chaining

        """
        if not isinstance(count, int) or count < 0:
            raise ValueError("Limit must be a non-negative integer")
        self._limit_value = count
        return self

    def build(self) -> tuple[str, dict[str, object]]:
        """
        Build the final query string and parameters.

        Returns:
            Tuple of (query string, parameters dict)

        """
        # Build SELECT clause
        select_clause = ", ".join(self._select_fields)

        # Build WHERE clause
        where_clause = ""
        if self._where_parts:
            where_clause = " WHERE " + " AND ".join(self._where_parts)

        # Build ORDER BY clause
        order_by_clause = ""
        if self._order_by:
            order_by_clause = " ORDER BY " + ", ".join(self._order_by)

        # Build LIMIT clause
        limit_clause = ""
        if self._limit_value is not None:
            limit_param = self._add_param(self._limit_value)
            limit_clause = " LIMIT " + limit_param

        # Build query safely without f-string interpolation
        query_parts = [
            "SELECT",
            select_clause,
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


class VectorQueryBuilder(QueryBuilder):
    """Specialized query builder for vector similarity search."""

    def __init__(self) -> None:
        """Initialize vector query builder."""
        super().__init__("knowledge_chunk")
        self._embedding_param: str | None = None

    def with_embedding_similarity(
        self, query_embedding: list[float]
    ) -> "VectorQueryBuilder":
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
                "cosine_similarity(embedding,",
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

    def __init__(self) -> None:
        """Initialize fulltext query builder."""
        super().__init__("knowledge_chunk")
        self._query_text_param: str | None = None

    def search(self, query_text: str) -> "FullTextQueryBuilder":
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
            text_field = sanitize_field_name("text")
            self._where_parts.insert(0, f"{text_field} @@ {self._query_text_param}")

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
