"""Tests for VectorQueryBuilder."""

from db.specialized_builders import VectorQueryBuilder


class TestVectorQueryBuilder:
    """Test cases for VectorQueryBuilder."""

    def test_basic_vector_query(self) -> None:
        """Test basic vector similarity query."""
        embedding = [0.1, 0.2, 0.3]
        builder = VectorQueryBuilder("test_table").with_embedding_similarity(embedding)
        query, params = builder.build()

        assert "SELECT" in query
        assert "cosine_similarity" in query
        assert "similarity_score" in query
        assert "FROM test_table" in query
        assert "param_0" in params
        assert params["param_0"] == embedding

    def test_vector_with_where(self) -> None:
        """Test vector query with WHERE conditions."""
        embedding = [0.1, 0.2, 0.3]
        builder = (
            VectorQueryBuilder("test_table")
            .with_embedding_similarity(embedding)
            .where_eq("tenant_id", "t1")
            .where_is_not_none("embedding")
        )
        query, _params = builder.build()

        assert "cosine_similarity" in query
        assert "WHERE" in query
        assert "tenant_id" in query
        assert "embedding IS NOT NONE" in query

    def test_vector_order_by_similarity(self) -> None:
        """Test vector query with automatic ORDER BY similarity."""
        embedding = [0.1, 0.2, 0.3]
        builder = (
            VectorQueryBuilder("test_table")
            .with_embedding_similarity(embedding)
            .limit(10)
        )
        query, _params = builder.build()

        assert "ORDER BY similarity_score DESC" in query

    def test_vector_with_custom_order_by(self) -> None:
        """Test vector query with custom ORDER BY."""
        embedding = [0.1, 0.2, 0.3]
        builder = (
            VectorQueryBuilder("test_table")
            .with_embedding_similarity(embedding)
            .order_by("created_at", "DESC")
        )
        query, _params = builder.build()

        assert "ORDER BY created_at DESC" in query
        assert "similarity_score" not in query
