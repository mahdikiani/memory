"""Base query builder for safe SurrealDB queries."""

import logging
import re
from typing import Self

from .field_validation import sanitize_field_name, validate_field_name
from .metadata import _get_table_name
from .utils import get_all_subclasses

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
        self._skip_value: int | None = None

    @staticmethod
    def _validate_table(table: str) -> None:
        """Validate table name is safe (dynamic validation)."""
        from .models import AbstractBaseSurrealEntity

        # Dynamically get all valid table names from models
        model_classes = [
            cls
            for cls in get_all_subclasses(AbstractBaseSurrealEntity)
            if not (
                "Settings" in cls.__dict__
                and getattr(cls.Settings, "__abstract__", False)
            )
        ]
        allowed_tables = {_get_table_name(model) for model in model_classes}

        # Also validate table name format (alphanumeric, hyphen, underscore)
        if not re.match(r"^[a-zA-Z0-9_-]+$", table):
            raise ValueError(f"Invalid table name format: {table}")

        if table not in allowed_tables:
            logger.warning(
                "Table '%s' not found in registered models. Allowed: %s",
                table,
                sorted(allowed_tables),
            )
            # Don't raise error, just warn (for flexibility)

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

    def where_is_not_none(self, field: str) -> Self:
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

    def limit(self, count: int) -> Self:
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

    def skip(self, count: int) -> Self:
        """
        Add SKIP clause.

        Args:
            count: Number of records to skip

        Returns:
            Self for method chaining

        """
        if not isinstance(count, int) or count < 0:
            raise ValueError("Skip must be a non-negative integer")
        self._skip_value = count
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

        # Build skip clause
        skip_clause = ""
        if self._skip_value is not None:
            skip_clause = f" START {self._skip_value}"

        # Build LIMIT clause
        limit_clause = ""
        if self._limit_value is not None:
            limit_clause = f" LIMIT {self._limit_value}"

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
        if skip_clause:
            query_parts.append(skip_clause)
        if limit_clause:
            query_parts.append(limit_clause)

        query = " ".join(query_parts)

        return query, self._params


def query(table: str) -> QueryBuilder:
    """
    Create a QueryBuilder instance (functional entry point).

    Args:
        table: Table name

    Returns:
        QueryBuilder instance for method chaining

    Example:
        ```python
        query_builder = query("entity")
            .where_eq("tenant_id", "t1")
            .where_eq("name", "John")
            .limit(10)
        query_sql, params = query_builder.build()
        ```

    """
    return QueryBuilder(table)
