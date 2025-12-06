"""Hybrid retriever combining all search types."""

import logging

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from server.config import Settings

from .exact_match_retriever import ExactMatchRetriever
from .fulltext_retriever import FullTextRetriever
from .graph_retriever import GraphRetriever
from .vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


class HybridRetriever(BaseRetriever):
    """Hybrid retriever combining exact match, full text, vector, and graph search."""

    def __init__(
        self,
        tenant_id: str,
        use_exact_match: bool = True,
        use_fulltext: bool = True,
        use_vector: bool = True,
        use_graph: bool = True,
        exact_match_filters: dict[str, object] | None = None,
        vector_filters: dict[str, object] | None = None,
        entity_ids: list[str] | None = None,
        relation_type: str | None = None,
        limit_per_type: int = 5,
        settings: Settings | None = None,
    ) -> None:
        """
        Initialize hybrid retriever.

        Args:
            tenant_id: Tenant ID
            use_exact_match: Enable exact match search
            use_fulltext: Enable full text search
            use_vector: Enable vector search
            use_graph: Enable graph search
            exact_match_filters: Filters for exact match search
            vector_filters: Filters for vector search
            entity_ids: Entity IDs for graph traversal
            relation_type: Relation type filter for graph search
            limit_per_type: Maximum results per search type
            settings: Application settings

        """
        super().__init__()
        self.tenant_id = tenant_id
        self.limit_per_type = limit_per_type

        # Initialize retrievers
        self.retrievers: list[BaseRetriever] = []

        if use_exact_match:
            self.retrievers.append(
                ExactMatchRetriever(
                    tenant_id, exact_match_filters or {}, "chunks", limit_per_type
                )
            )

        if use_fulltext:
            self.retrievers.append(FullTextRetriever(tenant_id, {}, limit_per_type))

        if use_vector:
            self.retrievers.append(
                VectorRetriever(
                    tenant_id, vector_filters or {}, limit_per_type, settings
                )
            )

        if use_graph and entity_ids:
            self.retrievers.append(
                GraphRetriever(tenant_id, entity_ids, relation_type, 2, limit_per_type)
            )

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: object | None = None,
    ) -> list[Document]:
        """
        Get relevant documents using hybrid search.

        Args:
            query: Query string
            run_manager: LangChain run manager

        Returns:
            List of Document objects from all search types, deduplicated and ranked

        """
        all_documents: list[Document] = []

        # Run all retrievers in parallel
        for retriever in self.retrievers:
            try:
                docs = await retriever._aget_relevant_documents(
                    query, run_manager=run_manager
                )
                all_documents.extend(docs)
            except Exception as e:
                logger.warning("Retriever failed: %s", e)
                continue

        # Deduplicate by content and metadata
        seen = set()
        unique_documents: list[Document] = []

        for doc in all_documents:
            # Create a unique key from content and key metadata
            doc_key = (
                doc.page_content[:100],  # First 100 chars of content
                doc.metadata.get("chunk_id", ""),
                doc.metadata.get("entity_id", ""),
                doc.metadata.get("relation_id", ""),
            )
            if doc_key not in seen:
                seen.add(doc_key)
                unique_documents.append(doc)

        # Sort by relevance score if available
        def get_score(doc: Document) -> float:
            return (
                doc.metadata.get("similarity_score", 0.0)
                or doc.metadata.get("relevance_score", 0.0)
                or 0.5  # Default score for exact match/graph results
            )

        unique_documents.sort(key=get_score, reverse=True)

        logger.info(
            "Hybrid retriever found %d unique documents from %d total",
            len(unique_documents),
            len(all_documents),
        )

        return unique_documents
