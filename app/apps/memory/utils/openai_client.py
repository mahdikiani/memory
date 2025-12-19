"""Shared async OpenAI client factory (cached)."""

import logging
from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from server.config import Settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_async_client(api_key: str, base_url: str) -> AsyncOpenAI:
    """Get an async OpenAI client."""
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    logger.info("Initialized async OpenAI client base_url=%s", base_url)
    return client


@lru_cache(maxsize=4)
def get_client(api_key: str, base_url: str) -> OpenAI:
    """Get a sync OpenAI client."""
    client = OpenAI(api_key=api_key, base_url=base_url)
    logger.info("Initialized async OpenAI client base_url=%s", base_url)
    return client


def get_client_and_model(settings: Settings | None = None) -> tuple[AsyncOpenAI, str]:
    """Return cached async client and model name for a given settings."""
    if settings is None:
        settings = Settings()
    client = get_async_client(
        settings.openrouter_api_key, settings.openrouter_base_url
    )
    return client, settings.llm_model
