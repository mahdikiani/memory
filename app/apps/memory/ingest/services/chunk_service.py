"""Service for saving knowledge chunks to database."""

import logging

from server.db import db_manager

from ...models import KnowledgeChunk

logger = logging.getLogger(__name__)


async def save_chunks(chunks: list[KnowledgeChunk], source_id: str) -> int:
    """
    Save chunks to database.

    Args:
        chunks: List of chunks to save
        source_id: Source record ID

    Returns:
        Number of chunks saved

    """
    if not chunks:
        return 0

    db = db_manager.get_db()
    saved_count = 0

    for chunk in chunks:
        # Ensure source_id matches
        chunk.source_id = source_id

        # Generate record ID
        record_id = f"knowledge_chunk:{chunk.tenant_id}:{source_id}:{chunk.chunk_index}"

        try:
            # Create chunk record
            await db.create(record_id, chunk.model_dump(exclude={"id"}))
            saved_count += 1
            logger.debug("Saved chunk: %s", record_id)

        except Exception:
            logger.exception("Failed to save chunk: %s", record_id)
            continue

    logger.info("Saved %d chunks for source %s", saved_count, source_id)
    return saved_count
