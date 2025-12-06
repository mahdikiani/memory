"""Exact match retriever for SQL/relational queries."""

import logging

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from ...models import Entity, KnowledgeChunk, KnowledgeSource
from ...utils.query_executor import execute_exact_match_query

logger = logging.getLogger(__name__)


class ExactMatchRetriever(BaseRetriever):
    """Retriever for exact match queries using SurrealQL."""

    def __init__(
        self,
        tenant_id: str,
        filters: dict[str, object],
        search_type: str = "chunks",  # "entities", "sources", or "chunks"
        limit: int = 20,
    ) -> None:
        """
        Initialize exact match retriever.

        Args:
            tenant_id: Tenant ID
            filters: Dictionary of field filters for exact matching
            search_type: Type of search ("entities", "sources", or "chunks")
            limit: Maximum number of results

        """
        super().__init__()
        self.tenant_id = tenant_id
        self.filters = filters
        self.search_type = search_type
        self.limit = limit

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: object | None = None,
    ) -> list[Document]:
        """
        Get relevant documents using exact match search.

        Args:
            query: Query string (not used for exact match, but required by interface)
            run_manager: LangChain run manager

        Returns:
            List of Document objects

        """
        documents: list[Document] = []

        try:
            # Map search_type to table name
            table_map = {
                "entities": "entity",
                "sources": "knowledge_source",
                "chunks": "knowledge_chunk",
            }

            table = table_map.get(self.search_type, "knowledge_chunk")
            rows = await execute_exact_match_query(
                table, self.filters, self.tenant_id, self.limit
            )

            for row in rows:
                if self.search_type == "entities":
                    entity = Entity(**row)
                    doc = Document(
                        page_content=(f"Entity: {entity.name} ({entity.entity_type})"),
                        metadata={
                            "type": "entity",
                            "entity_id": entity.id or "",
                            "entity_type": entity.entity_type,
                            "name": entity.name,
                            "attributes": entity.attributes,
                        },
                    )
                    documents.append(doc)

                elif self.search_type == "sources":
                    source = KnowledgeSource(**row)
                    doc = Document(
                        page_content=(
                            f"Source: {source.source_id} ({source.source_type})"
                        ),
                        metadata={
                            "type": "source",
                            "source_id": source.id or "",
                            "source_type": source.source_type,
                            "sensor_name": source.sensor_name,
                        },
                    )
                    documents.append(doc)

                else:  # chunks
                    chunk = KnowledgeChunk(**row)
                    doc = Document(
                        page_content=chunk.text,
                        metadata={
                            "type": "chunk",
                            "chunk_id": chunk.id or "",
                            "source_id": chunk.source_id,
                            "chunk_index": chunk.chunk_index,
                        },
                    )
                    documents.append(doc)

            logger.debug("Exact match retriever found %d documents", len(documents))

        except Exception:
            logger.exception("Failed to retrieve documents")
            return []

        return documents
