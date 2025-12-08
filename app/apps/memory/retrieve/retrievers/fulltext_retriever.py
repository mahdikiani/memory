"""Full text search retriever for LangChain."""

import logging

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from db import execute_fulltext_query

from ...models import KnowledgeChunk

logger = logging.getLogger(__name__)


class FullTextRetriever(BaseRetriever):
    """Retriever for full text search."""

    def __init__(
        self,
        tenant_id: str,
        filters: dict[str, object] | None = None,
        limit: int = 10,
    ) -> None:
        """
        Initialize full text retriever.

        Args:
            tenant_id: Tenant ID
            filters: Optional filters (source_type, source_id, etc.)
            limit: Maximum number of results

        """
        super().__init__()
        self.tenant_id = tenant_id
        self.filters = filters or {}
        self.limit = limit

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: object = None,
    ) -> list[Document]:
        """
        Get relevant documents using full text search.

        Args:
            query: Query text to search for
            run_manager: LangChain run manager

        Returns:
            List of Document objects with relevance scores

        """
        documents: list[Document] = []

        try:
            rows = await execute_fulltext_query(
                query, self.filters, self.tenant_id, self.limit
            )

            for row in rows:
                relevance_score = row.pop("relevance_score", 0.0)
                chunk = KnowledgeChunk(**row)
                doc = Document(
                    page_content=chunk.text,
                    metadata={
                        "type": "chunk",
                        "chunk_id": chunk.id or "",
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "relevance_score": relevance_score,
                    },
                )
                documents.append(doc)

            logger.debug("Full text retriever found %d documents", len(documents))

        except Exception:
            logger.exception("Failed to perform full text search")
            # Fallback to LIKE search (also uses safe query builder)
            return await self._fallback_like_search(query)

        return documents

    async def _fallback_like_search(self, query_text: str) -> list[Document]:
        """Fallback to LIKE-based search with safe parameterization."""
        from db import execute_query, query

        documents: list[Document] = []

        # Build safe WHERE clause
        filters = self.filters.copy()
        # Add text filter for LIKE search

        # Build query using ORM-like builder (no string interpolation!)

        query_builder = (
            query("knowledge_chunk")
            .where_eq("tenant_id", self.tenant_id)
            .where_eq("is_deleted", False)
            .where("text", query_text, operator="~")
            .limit(self.limit)
        )

        # Add filters
        for field, value in filters.items():
            if isinstance(value, list):
                query_builder.where_in(field, value)
            else:
                query_builder.where_eq(field, value)

        query_sql, params = query_builder.build()

        try:
            rows = await execute_query(query_sql, params)
            for row in rows:
                chunk = KnowledgeChunk(**row)
                score = 1.0 if query_text.lower() in chunk.text.lower() else 0.5
                doc = Document(
                    page_content=chunk.text,
                    metadata={
                        "type": "chunk",
                        "chunk_id": chunk.id or "",
                        "source_id": chunk.source_id,
                        "chunk_index": chunk.chunk_index,
                        "relevance_score": score,
                    },
                )
                documents.append(doc)
        except Exception:
            logger.exception("Failed fallback fulltext search")
            return []

        return documents
