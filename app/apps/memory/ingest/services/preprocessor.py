"""Preprocessor service for chunks (embedding generation, fulltext preparation)."""

import logging

from server.config import Settings

from ...models import KnowledgeChunk
from ...utils.embedding_service import generate_embeddings_batch

logger = logging.getLogger(__name__)


async def preprocess_chunks(
    chunks: list[KnowledgeChunk],
    settings: Settings | None = None,
) -> list[KnowledgeChunk]:
    """
    Preprocess chunks: generate embeddings and prepare for storage.

    Args:
        chunks: List of chunks to preprocess
        settings: Application settings

    Returns:
        List of chunks with embeddings generated

    """
    if not chunks:
        return []

    # Extract texts for batch embedding generation
    texts = [chunk.text for chunk in chunks]

    try:
        # Generate embeddings in batch
        embeddings = await generate_embeddings_batch(texts, settings=settings)

        # Assign embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            chunk.embedding = embedding

        logger.info("Preprocessed %d chunks with embeddings", len(chunks))

    except Exception:
        logger.exception("Failed to preprocess chunks")
        # Continue without embeddings if generation fails
        for chunk in chunks:
            chunk.embedding = None

    return chunks
