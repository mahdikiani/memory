"""LangChain chains for knowledge ingestion and entity extraction."""

import json
import logging

from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAI

from prompts.services import PromptService
from server.config import Settings

logger = logging.getLogger(__name__)


class IngestionChain:
    """Chain for extracting entities and relations from text using LLM."""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize ingestion chain.

        Args:
            settings: Application settings (defaults to Settings() if not provided)

        """
        if settings is None:
            settings = Settings()

        self.settings = settings
        self.client: OpenAI | None = None
        self.prompt_service = PromptService(settings)
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize OpenAI client configured for OpenRouter."""
        self.client = OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )
        logger.info(
            "Initialized ingestion chain with model: %s", self.settings.llm_model
        )

    async def extract_entities(
        self,
        text: str,
        tenant_id: str,
        allowed_entity_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """
        Extract entities from text using LLM.

        Args:
            text: Text content to analyze
            tenant_id: Tenant ID for context
            allowed_entity_types: Optional list of allowed entity types

        Returns:
            List of extracted entities with type, name, and attributes

        """
        prompt_config = await self.prompt_service.get_prompt("entity_extraction")

        # Add allowed types to prompt if provided
        system_prompt = prompt_config["system"]
        if allowed_entity_types:
            types_str = ", ".join(allowed_entity_types)
            system_prompt += (
                f"\n\nIMPORTANT: Only extract entities of these types: {types_str}. "
                "Ignore any other entity types."
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", prompt_config["human"]),
        ])

        try:
            messages = prompt.format_messages(text=text)
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": msg.type, "content": msg.content} for msg in messages
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistent extraction
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from LLM for entity extraction")
                return []

            # Parse JSON response
            result = json.loads(content)
            entities = result.get("entities", [])
            if not isinstance(entities, list):
                entities = [entities] if entities else []

            logger.info("Extracted %d entities from text", len(entities))

        except Exception:
            logger.exception("Failed to extract entities")
            return []

        return entities

    async def extract_relations(
        self,
        text: str,
        entities: list[dict[str, object]],
        tenant_id: str,
        allowed_relation_types: list[str] | None = None,
    ) -> list[dict[str, object]]:
        """
        Extract relations between entities using LLM.

        Args:
            text: Original text content
            entities: List of extracted entities
            tenant_id: Tenant ID for context
            allowed_relation_types: Optional list of allowed relation types

        Returns:
            List of relations with from_entity, to_entity, and relation_type

        """
        if len(entities) < 2:
            return []

        prompt_config = await self.prompt_service.get_prompt("relation_extraction")

        # Add allowed types to prompt if provided
        system_prompt = prompt_config["system"]
        if allowed_relation_types:
            types_str = ", ".join(allowed_relation_types)
            system_prompt += (
                f"\n\nIMPORTANT: Only extract relations of these types: {types_str}. "
                "Ignore object other relation types."
            )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", prompt_config["human"]),
        ])

        try:
            entities_str = json.dumps(entities, indent=2)
            messages = prompt.format_messages(text=text, entities=entities_str)
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": msg.type, "content": msg.content} for msg in messages
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from LLM for relation extraction")
                return []

            # Parse JSON response
            result = json.loads(content)
            relations = result.get("relations", [])
            if not isinstance(relations, list):
                relations = [relations] if relations else []

            logger.info("Extracted %d relations from text", len(relations))

        except Exception:
            logger.exception("Failed to extract relations")
            return []

        return relations

    async def process_text(
        self,
        text: str,
        tenant_id: str,
        allowed_entity_types: list[str] | None = None,
        allowed_relation_types: list[str] | None = None,
    ) -> dict[str, object]:
        """
        Process text to extract entities and relations.

        Args:
            text: Text content to process
            tenant_id: Tenant ID for context
            allowed_entity_types: Optional list of allowed entity types
            allowed_relation_types: Optional list of allowed relation types

        Returns:
            Dictionary with 'entities' and 'relations' lists

        """
        entities = await self.extract_entities(text, tenant_id, allowed_entity_types)
        relations = await self.extract_relations(
            text, entities, tenant_id, allowed_relation_types
        )

        return {
            "entities": entities,
            "relations": relations,
        }
