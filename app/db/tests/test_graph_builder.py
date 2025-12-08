"""Tests for GraphQueryBuilder."""

import pytest

from db.specialized_builders import GraphQueryBuilder


class TestGraphQueryBuilder:
    """Test cases for GraphQueryBuilder."""

    def test_basic_graph_query(self) -> None:
        """Test basic graph traversal query."""
        builder = (
            GraphQueryBuilder("entity", "relation")
            .from_entities(["entity:1", "entity:2"])
            .max_depth(2)
        )
        query, params = builder.build()

        assert "SELECT" in query
        assert "FROM entity" in query
        assert "->->" in query
        assert "relation" in query
        assert "param_0" in params
        assert params["param_0"] == "entity:1"

    def test_graph_with_depth_range(self) -> None:
        """Test graph query with depth range."""
        builder = (
            GraphQueryBuilder("entity", "relation")
            .from_entities(["entity:1"])
            .depth_range(3, 5)
        )
        query, _params = builder.build()

        assert "UNION ALL" in query
        assert "distance" in query
        assert "3 AS distance" in query
        assert "5 AS distance" in query

    def test_graph_order_by_distance(self) -> None:
        """Test graph query with distance ordering."""
        builder = (
            GraphQueryBuilder("entity", "relation")
            .from_entities(["entity:1"])
            .depth_range(2, 4)
            .order_by_distance()
        )
        query, _params = builder.build()

        assert "ORDER BY distance ASC" in query

    def test_graph_with_where(self) -> None:
        """Test graph query with WHERE conditions."""
        builder = (
            GraphQueryBuilder("entity", "relation")
            .from_entities(["entity:1"])
            .where("tenant_id", "t1")
            .where("is_deleted", False)
        )
        query, _params = builder.build()

        assert "WHERE" in query
        assert "tenant_id" in query
        assert "is_deleted" in query

    def test_graph_with_to_entities(self) -> None:
        """Test graph query with target entities."""
        builder = (
            GraphQueryBuilder("entity", "relation")
            .from_entities(["entity:1"])
            .to_entities(["entity:10", "entity:11"])
            .max_depth(3)
        )
        query, _params = builder.build()

        assert "WHERE" in query
        assert "id IN" in query

    def test_graph_min_max_depth_validation(self) -> None:
        """Test graph query depth validation."""
        builder = GraphQueryBuilder("entity", "relation")

        with pytest.raises(ValueError, match="Depth must be an integer"):
            builder.max_depth(0)

        with pytest.raises(ValueError, match="Depth must be an integer"):
            builder.max_depth(11)

        with pytest.raises(ValueError, match="min_depth must be <= max_depth"):
            builder.depth_range(5, 3)

    def test_graph_no_from_entities(self) -> None:
        """Test graph query without from_entities raises error."""
        builder = GraphQueryBuilder("entity", "relation")

        with pytest.raises(ValueError, match="At least one starting entity"):
            builder.build()
