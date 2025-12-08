"""Tests for FullTextQueryBuilder."""

from db.specialized_builders import FullTextQueryBuilder


class TestFullTextQueryBuilder:
    """Test cases for FullTextQueryBuilder."""

    def test_basic_fulltext_query(self) -> None:
        """Test basic fulltext search query."""
        builder = FullTextQueryBuilder("test_table").search("search text")
        query, params = builder.build()

        assert "SELECT" in query
        assert "search::score(0)" in query
        assert "relevance_score" in query
        assert "FROM test_table" in query
        assert "@@" in query
        assert "param_0" in params
        assert params["param_0"] == "search text"

    def test_fulltext_with_where(self) -> None:
        """Test fulltext query with WHERE conditions."""
        builder = (
            FullTextQueryBuilder("test_table")
            .search("search text")
            .where_eq("tenant_id", "t1")
            .where_eq("is_deleted", False)
        )
        query, _params = builder.build()

        assert "@@" in query
        assert "WHERE" in query
        assert "tenant_id" in query

    def test_fulltext_order_by_relevance(self) -> None:
        """Test fulltext query with automatic ORDER BY relevance."""
        builder = FullTextQueryBuilder("test_table").search("search text").limit(10)
        query, _params = builder.build()

        assert "ORDER BY relevance_score DESC" in query

    def test_fulltext_with_custom_order_by(self) -> None:
        """Test fulltext query with custom ORDER BY."""
        builder = (
            FullTextQueryBuilder("test_table")
            .search("search text")
            .order_by("created_at", "DESC")
        )
        query, _params = builder.build()

        assert "ORDER BY created_at DESC" in query
        assert "relevance_score" not in query
