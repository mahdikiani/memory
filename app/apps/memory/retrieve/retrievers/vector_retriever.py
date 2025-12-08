"""Vector search retriever for LangChain."""

import logging

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from db import execute_query, execute_vector_query
from server.config import Settings

from ...models import KnowledgeChunk
from ...utils.embedding_service import generate_embedding

logger = logging.getLogger(__name__)


class VectorRetriever(BaseRetriever):
    """Retriever for vector/semantic search."""

    def __init__(
        self,
        tenant_id: str,
        filters: dict[str, object] | None = None,
        limit: int = 10,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize vector retriever.

        Args:
            tenant_id: Tenant ID
            filters: Optional filters (source_type, source_id, etc.)
            limit: Maximum number of results
            settings: Application settings

        """
        super().__init__()
        self.tenant_id = tenant_id
        self.filters = filters or {}
        self.limit = limit
        self.settings = settings

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: object | None = None
    ) -> list[Document]:
        """
        Get relevant documents using vector similarity search.

        Args:
            query: Query text to search for
            run_manager: LangChain run manager

        Returns:
            List of Document objects with similarity scores

        """
        documents: list[Document] = []

        try:
            # Generate embedding for query
            query_embedding = await generate_embedding(query, settings=self.settings)

            # Search using vector similarity with safe parameterized query
            rows = await execute_vector_query(
                query_embedding, self.filters, self.tenant_id, self.limit
            )

            for row in rows:
                similarity_score = row.pop("similarity_score", 0.0)
                chunk = KnowledgeChunk(**row)
                doc = Document(
                    page_content=chunk.text,
                    metadata={
                        "type": "chunk",
                        "chunk_id": chunk.id or "",
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "similarity_score": similarity_score,
                    },
                )
                documents.append(doc)

            logger.debug("Vector retriever found %d documents", len(documents))

        except Exception:
            logger.exception("Failed to retrieve documents")
            # Fallback to manual cosine similarity
            return await self._fallback_vector_search(query)

        return documents

    async def _fallback_vector_search(self, query: str) -> list[Document]:
        """Fallback using cosine_similarity function in SurrealDB."""
        from db import VectorQueryBuilder

        documents: list[Document] = []

        try:
            # Generate embedding
            query_embedding = await generate_embedding(query, settings=self.settings)

            # Use VectorQueryBuilder which uses cosine_similarity function in DB
            query_builder = (
                VectorQueryBuilder()
                .with_embedding_similarity(query_embedding)
                .where_eq("tenant_id", self.tenant_id)
                .where_eq("is_deleted", False)
                .where_not_none("embedding")
                .limit(self.limit)
            )

            # Add filters
            for field, value in self.filters.items():
                if isinstance(value, list):
                    query_builder.where_in(field, value)
                else:
                    query_builder.where_eq(field, value)

            query_sql, params = query_builder.build()
            rows = await execute_query(query_sql, params)

            # Convert to documents
            for row in rows:
                similarity_score = row.pop("similarity_score", 0.0)
                chunk = KnowledgeChunk(**row)
                doc = Document(
                    page_content=chunk.text,
                    metadata={
                        "type": "chunk",
                        "chunk_id": chunk.id or "",
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "similarity_score": similarity_score,
                    },
                )
                documents.append(doc)

        except Exception:
            logger.exception("Failed fallback vector search")
            return []

        return documents
