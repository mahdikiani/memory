"""Graph search retriever for LangChain."""

import logging

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from server.db import db_manager

from ...models import Entity, Relation
from ...utils.query_executor import execute_graph_query

logger = logging.getLogger(__name__)


class GraphRetriever(BaseRetriever):
    """Retriever for graph-based search and traversal."""

    def __init__(
        self,
        tenant_id: str,
        entity_ids: list[str] | None = None,
        relation_type: str | None = None,
        max_depth: int = 2,
        limit: int = 10,
    ) -> None:
        """
        Initialize graph retriever.

        Args:
            tenant_id: Tenant ID
            entity_ids: Optional list of entity IDs to start traversal from
            relation_type: Optional filter by relation type
            max_depth: Maximum traversal depth
            limit: Maximum number of results

        """
        super().__init__()
        self.tenant_id = tenant_id
        self.entity_ids = entity_ids or []
        self.relation_type = relation_type
        self.max_depth = max_depth
        self.limit = limit

    def _validate_entity_id(self, entity_id: str) -> bool:
        """
        Validate entity ID format.

        Args:
            entity_id: Entity ID to validate

        Returns:
            True if valid, False otherwise

        """
        if not isinstance(entity_id, str):
            return False
        # Basic validation - should not contain SQL keywords
        if any(
            keyword in entity_id.upper()
            for keyword in ["SELECT", "DROP", "DELETE", "INSERT", "UPDATE"]
        ):
            logger.warning("Suspicious entity_id detected: %s", entity_id)
            return False
        return True

    async def _fetch_related_entities(
        self, relation: Relation, all_entities: list[Entity]
    ) -> None:
        """
        Fetch entities related to a relation.

        Args:
            relation: Relation to get entities from
            all_entities: List to append fetched entities to

        """
        db = db_manager.get_db()
        related_ids = [relation.from_entity_id, relation.to_entity_id]

        for rid in related_ids:
            if not self._validate_entity_id(rid):
                continue

            try:
                entity_result = await db.select(rid)
                if entity_result:
                    entity = Entity(**entity_result)
                    if entity not in all_entities:
                        all_entities.append(entity)
            except Exception as e:
                logger.debug("Failed to fetch entity %s: %s", rid, e)

    @staticmethod
    def _entity_to_document(entity: Entity) -> Document:
        """
        Convert entity to Document.

        Args:
            entity: Entity to convert

        Returns:
            Document object

        """
        return Document(
            page_content=f"Entity: {entity.name} ({entity.entity_type})",
            metadata={
                "type": "entity",
                "entity_id": entity.id or "",
                "entity_type": entity.entity_type,
                "name": entity.name,
                "attributes": entity.attributes,
            },
        )

    @staticmethod
    def _relation_to_document(relation: Relation) -> Document:
        """
        Convert relation to Document.

        Args:
            relation: Relation to convert

        Returns:
            Document object

        """
        return Document(
            page_content=(
                f"Relation: {relation.from_entity_id} "
                f"{relation.relation_type} {relation.to_entity_id}"
            ),
            metadata={
                "type": "relation",
                "relation_id": relation.id or "",
                "from_entity_id": relation.from_entity_id,
                "to_entity_id": relation.to_entity_id,
                "relation_type": relation.relation_type,
                "attributes": relation.attributes,
            },
        )

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: object | None = None,
    ) -> list[Document]:
        """
        Get relevant documents using graph traversal.

        Args:
            query: Query string (used to find starting entities if "
            "entity_ids not provided)
            run_manager: LangChain run manager

        Returns:
            List of Document objects representing entities and relations

        """
        if not self.entity_ids:
            logger.warning(
                "Graph retriever needs entity_ids or entity extraction from query"
            )
            return []

        try:
            all_entities: list[Entity] = []
            all_relations: list[Relation] = []

            # Use safe parameterized query to get relations
            relation_rows = await execute_graph_query(
                self.tenant_id,
                self.entity_ids,
                self.relation_type,
                self.max_depth * 10,
            )

            # Process relations and fetch related entities
            for row in relation_rows:
                relation = Relation(**row)
                all_relations.append(relation)
                await self._fetch_related_entities(relation, all_entities)

            # Convert to documents
            documents: list[Document] = []
            documents.extend(
                self._entity_to_document(entity)
                for entity in all_entities[: self.limit]
            )
            documents.extend(
                self._relation_to_document(relation)
                for relation in all_relations[: self.limit]
            )

            logger.debug("Graph retriever found %d documents", len(documents))
            return documents[: self.limit]

        except Exception:
            logger.exception("Failed to retrieve documents")
            return []
