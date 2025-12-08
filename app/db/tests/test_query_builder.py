"""Tests for QueryBuilder."""

import pytest

from db.query_builder import QueryBuilder


class TestQueryBuilder:
    """Test cases for QueryBuilder."""

    def test_basic_query(self) -> None:
        """Test basic query building."""
        builder = QueryBuilder("test_table")
        query, params = builder.build()

        assert "SELECT" in query
        assert "FROM test_table" in query
        assert params == {}

    def test_where_eq(self) -> None:
        """Test WHERE equality condition."""
        builder = QueryBuilder("test_table").where_eq("name", "John")
        query, params = builder.build()

        assert "WHERE" in query
        assert "name" in query
        assert "param_0" in params
        assert params["param_0"] == "John"

    def test_where_in(self) -> None:
        """Test WHERE IN condition."""
        builder = QueryBuilder("test_table").where_in("status", ["active", "pending"])
        query, params = builder.build()

        assert "WHERE" in query
        assert "IN" in query
        assert "param_0" in params
        assert params["param_0"] == ["active", "pending"]

    def test_multiple_where(self) -> None:
        """Test multiple WHERE conditions."""
        builder = (
            QueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .where_eq("is_deleted", False)
        )
        query, params = builder.build()

        assert "WHERE" in query
        assert "AND" in query
        assert len(params) == 2

    def test_order_by(self) -> None:
        """Test ORDER BY clause."""
        builder = QueryBuilder("test_table").order_by("created_at", "DESC")
        query, _params = builder.build()

        assert "ORDER BY" in query
        assert "created_at DESC" in query

    def test_limit(self) -> None:
        """Test LIMIT clause."""
        builder = QueryBuilder("test_table").limit(10)
        query, params = builder.build()

        assert "LIMIT" in query
        assert "param_0" in params
        assert params["param_0"] == 10

    def test_select_fields(self) -> None:
        """Test SELECT specific fields."""
        builder = QueryBuilder("test_table").select("id", "name", "email")
        query, _params = builder.build()

        assert "SELECT" in query
        assert "id" in query
        assert "name" in query
        assert "email" in query
        assert "*" not in query

    def test_where_is_none(self) -> None:
        """Test WHERE IS NONE condition."""
        builder = QueryBuilder("test_table").where_is_none("deleted_at")
        query, _params = builder.build()

        assert "WHERE" in query
        assert "deleted_at IS NONE" in query

    def test_where_is_not_none(self) -> None:
        """Test WHERE IS NOT NONE condition."""
        builder = QueryBuilder("test_table").where_is_not_none("email")
        query, _params = builder.build()

        assert "WHERE" in query
        assert "email IS NOT NONE" in query

    def test_where_not_in(self) -> None:
        """Test WHERE NOT IN condition."""
        builder = QueryBuilder("test_table").where_not_in("status", ["deleted"])
        query, params = builder.build()

        assert "WHERE" in query
        assert "NOT IN" in query
        assert "param_0" in params

    def test_complex_query(self) -> None:
        """Test complex query with multiple clauses."""
        builder = (
            QueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .where_in("status", ["active", "pending"])
            .where_is_not_none("email")
            .order_by("created_at", "DESC")
            .limit(20)
        )
        query, params = builder.build()

        assert "WHERE" in query
        assert "AND" in query
        assert "ORDER BY" in query
        assert "LIMIT" in query
        assert len(params) == 3

    def test_unsafe_field_name(self) -> None:
        """Test validation of unsafe field names."""
        builder = QueryBuilder("test_table")

        with pytest.raises(ValueError, match="Unsafe field name"):
            builder.where("'; DROP TABLE test_table; --", "value")

    def test_unsafe_operator(self) -> None:
        """Test validation of unsafe operators."""
        builder = QueryBuilder("test_table")

        with pytest.raises(ValueError, match="Unsafe operator"):
            builder.where("name", "John", operator="; DROP TABLE")
