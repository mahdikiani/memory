"""LLM helpers for ingestion (entity/relation extraction)."""

import json
import logging
from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate

from prompts.services import PromptService
from server.config import Settings

from ..utils.openai_client import get_client_and_model

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def _get_prompt_service(settings: Settings) -> PromptService:
    return PromptService(settings)


async def extract_entities(
    text: str,
    tenant_id: str,
    allowed_entity_types: list[str] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    """Extract entities from text using LLM."""
    if settings is None:
        settings = Settings()

    prompt_service = _get_prompt_service(settings)
    prompt_config = await prompt_service.get_prompt("entity_extraction")

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
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from LLM for entity extraction")
            return []

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
    text: str,
    entities: list[dict[str, object]],
    tenant_id: str,
    allowed_relation_types: list[str] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, object]]:
    """Extract relations between entities using LLM."""
    if len(entities) < 2:
        return []

    if settings is None:
        settings = Settings()

    prompt_service = _get_prompt_service(settings)
    prompt_config = await prompt_service.get_prompt("relation_extraction")

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
        client, model_name = get_client_and_model(settings)
        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": msg.type, "content": msg.content} for msg in messages],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("Empty response from LLM for relation extraction")
            return []

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
    text: str,
    tenant_id: str,
    allowed_entity_types: list[str] | None = None,
    allowed_relation_types: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Process text to extract entities and relations."""
    entities = await extract_entities(text, tenant_id, allowed_entity_types, settings)
    relations = await extract_relations(
        text, entities, tenant_id, allowed_relation_types, settings
    )

    return {
        "entities": entities,
        "relations": relations,
    }
