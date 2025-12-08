"""LLM helpers for query classification and filter extraction."""

import json
import logging
from functools import lru_cache
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate

from prompts.services import PromptService
from server.config import Settings

from ..utils.openai_client import get_client_and_model

logger = logging.getLogger(__name__)

QueryType = Literal["structured", "semantic", "hybrid"]


@lru_cache(maxsize=4)
def _get_prompt_service(settings: Settings) -> PromptService:
    return PromptService(settings)


async def classify_query(
    question: str,
    settings: Settings | None = None,
) -> QueryType:
    """Classify query type: structured, semantic, or hybrid."""
    if settings is None:
        settings = Settings()

    prompt_service = _get_prompt_service(settings)
    prompt_config = await prompt_service.get_prompt("query_classification")
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_config["system"]),
        ("human", prompt_config["human"]),
    ])

    try:
        messages = prompt.format_messages(question=question)
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from LLM for query classification")
            return "hybrid"

        classification = content.strip().lower()
        if classification in ("structured", "semantic", "hybrid"):
            logger.debug("Classified query as: %s", classification)
            return classification  # type: ignore

        logger.warning(
            "Unexpected classification '%s', defaulting to hybrid", classification
        )

    except Exception:
        logger.exception("Failed to classify query")
        return "hybrid"

    return "hybrid"


async def extract_filters(
    question: str,
    hints: dict[str, object] | None = None,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Extract filters and hints from query."""
    if settings is None:
        settings = Settings()

    prompt_service = _get_prompt_service(settings)
    prompt_config = await prompt_service.get_prompt("filter_extraction")
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_config["system"]),
        ("human", prompt_config["human"]),
    ])

    try:
        hints_str = json.dumps(hints or {})
        messages = prompt.format_messages(question=question, hints=hints_str)
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
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
