"""Embedding helpers for generating vector embeddings (async, functional style)."""

import logging
from collections.abc import Iterable

from server.config import Settings

from .openai_client import get_client_and_model

logger = logging.getLogger(__name__)


async def generate_embedding(
    text: str, settings: Settings | None = None
) -> list[float]:
    """Generate an embedding for a single text (async)."""
    if not text.strip():
        raise ValueError("Cannot generate embedding for empty text")

    client, model_name = get_client_and_model(settings)
    try:
        response = await client.embeddings.create(model=model_name, input=text)
        embedding = response.data[0].embedding
        logger.debug("Generated embedding of dimension %d", len(embedding))
    except Exception:
        logger.exception("Failed to generate embedding")
        raise

    return embedding


async def generate_embeddings_batch(
    texts: Iterable[str],
    settings: Settings | None = None,
    batch_size: int = 100,
) -> list[list[float]]:
    """Generate embeddings for multiple texts in batches (async)."""
    texts_list = list(texts)
    if not texts_list:
        return []

    # Filter out empty texts
    valid_texts = [text for text in texts_list if text.strip()]
    if len(valid_texts) != len(texts_list):
        logger.warning(
            "Filtered out %d empty texts from batch",
            len(texts_list) - len(valid_texts),
        )

    if not valid_texts:
        return []

    client, model_name = get_client_and_model(settings)
    embeddings: list[list[float]] = []

    for i in range(0, len(valid_texts), batch_size):
        batch = valid_texts[i : i + batch_size]
        try:
            response = await client.embeddings.create(model=model_name, input=batch)
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
            logger.debug(
                "Generated embeddings for batch %d-%d (%d texts)",
                i,
                min(i + batch_size, len(valid_texts)),
                len(batch),
            )
        except Exception:
            logger.exception("Failed to generate embeddings for batch")
            raise

    logger.info("Generated %d embeddings total", len(embeddings))
    return embeddings
