"""Tests for CombinedQueryBuilder."""

import pytest

from db.specialized_builders import CombinedQueryBuilder


class TestCombinedQueryBuilder:
    """Test cases for CombinedQueryBuilder."""

    def test_combined_exact_match_only(self) -> None:
        """Test combined query with only exact match."""
        builder = (
            CombinedQueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .where_eq("is_deleted", False)
            .limit(10)
        )
        query, _params = builder.build()

        assert "SELECT" in query
        assert "FROM test_table" in query
        assert "WHERE" in query
        assert "LIMIT" in query

    def test_combined_with_vector(self) -> None:
        """Test combined query with vector search."""
        embedding = [0.1, 0.2, 0.3]
        builder = (
            CombinedQueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .with_vector_similarity(embedding)
            .limit(10)
        )
        query, _params = builder.build()

        assert "cosine_similarity" in query
        assert "similarity_score" in query
        assert "embedding IS NOT NONE" in query
        assert "ORDER BY similarity_score DESC" in query

    def test_combined_with_fulltext(self) -> None:
        """Test combined query with fulltext search."""
        builder = (
            CombinedQueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .with_fulltext_search("search text")
            .limit(10)
        )
        query, _params = builder.build()

        assert "@@" in query
        assert "search::score(0)" in query
        assert "relevance_score" in query
        assert "ORDER BY relevance_score DESC" in query

    def test_combined_vector_and_fulltext(self) -> None:
        """Test combined query with both vector and fulltext."""
        embedding = [0.1, 0.2, 0.3]
        builder = (
            CombinedQueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .with_vector_similarity(embedding)
            .with_fulltext_search("search text")
            .limit(10)
        )
        query, _params = builder.build()

        assert "cosine_similarity" in query
        assert "similarity_score" in query
        assert "@@" in query
        assert "relevance_score" in query
        assert "ORDER BY similarity_score DESC, relevance_score DESC" in query

    def test_combined_with_graph(self) -> None:
        """Test combined query with graph search."""
        builder = (
            CombinedQueryBuilder("test_table")
            .where_eq("tenant_id", "t1")
            .with_graph_search(
                entity_ids=["entity:1", "entity:2"],
                min_depth=3,
                max_depth=5,
                tenant_id="t1",
            )
        )
        queries = builder.build_all()

        assert "main" in queries
        assert "graph" in queries

        main_query, _main_params = queries["main"]
        graph_query, _graph_params = queries["graph"]

        assert "SELECT" in main_query
        assert "FROM test_table" in main_query
        assert "SELECT" in graph_query
        assert "distance" in graph_query

    def test_combined_build_all(self) -> None:
        """Test build_all method."""
        builder = CombinedQueryBuilder("test_table").where_eq("tenant_id", "t1")
        queries = builder.build_all()

        assert "main" in queries
        assert "graph" not in queries

        # Add graph search
        builder.with_graph_search(entity_ids=["entity:1"], tenant_id="t1")
        queries = builder.build_all()

        assert "main" in queries
        assert "graph" in queries

    def test_combined_vector_without_embedding(self) -> None:
        """Test combined query raises error if vector used without embedding."""
        builder = CombinedQueryBuilder("test_table")
        builder._use_vector = True

        with pytest.raises(ValueError, match="Vector search requires embedding"):
            builder.build()

    def test_combined_fulltext_without_query(self) -> None:
        """Test combined query raises error if fulltext used without query."""
        builder = CombinedQueryBuilder("test_table")
        builder._use_fulltext = True

        with pytest.raises(ValueError, match="Fulltext search requires query text"):
            builder.build()
