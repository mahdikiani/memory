"""LangChain chains for query classification and retrieval."""

import json
import logging
from typing import Literal

from langchain.prompts import ChatPromptTemplate
from openai import OpenAI

from apps.knowledge.services.prompt_service import PromptService
from server.config import Settings

logger = logging.getLogger(__name__)

QueryType = Literal["structured", "semantic", "hybrid"]


class RetrievalChain:
    """Chain for classifying queries and extracting filters for retrieval."""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize retrieval chain.

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
            "Initialized retrieval chain with model: %s", self.settings.llm_model
        )

    async def classify_query(self, question: str) -> QueryType:
        """
        Classify query type: structured, semantic, or hybrid.

        Args:
            question: User question

        Returns:
            Query type classification

        """
        prompt_config = await self.prompt_service.get_prompt("query_classification")
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_config["system"]),
            ("human", prompt_config["human"]),
        ])

        try:
            messages = prompt.format_messages(question=question)
            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=[
                    {"role": msg.type, "content": msg.content} for msg in messages
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("Empty response from LLM for query classification")
                return "hybrid"  # Default to hybrid

            classification = content.strip().lower()
            if classification in ("structured", "semantic", "hybrid"):
                logger.debug("Classified query as: %s", classification)
                return classification  # type: ignore

            logger.warning(
                "Unexpected classification '%s', defaulting to hybrid", classification
            )

        except Exception:
            logger.exception("Failed to classify query")
            return "hybrid"  # Default to hybrid on error

        return "hybrid"

    async def extract_filters(
        self, question: str, hints: dict[str, object] | None = None
    ) -> dict[str, object]:
        """
        Extract filters and hints from query.

        Args:
            question: User question
            hints: Optional hints provided by user

        Returns:
            Dictionary with extracted filters (entity names, time ranges, etc.)

        """
        prompt_config = await self.prompt_service.get_prompt("filter_extraction")
        prompt = ChatPromptTemplate.from_messages([
            ("system", prompt_config["system"]),
            ("human", prompt_config["human"]),
        ])

        try:
            hints_str = json.dumps(hints or {})
            messages = prompt.format_messages(question=question, hints=hints_str)
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
                logger.warning("Empty response from LLM for filter extraction")
                return {}

            filters = json.loads(content)
            logger.debug("Extracted filters: %s", filters)

        except Exception:
            logger.exception("Failed to extract filters")
            return {}

        return filters
