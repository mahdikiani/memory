"""Shared utilities for ingestion processors."""

import logging
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ...models import ArtifactChunk
from ...utils.embedding import generate_embeddings_batch

logger = logging.getLogger(__name__)


class TextProcessor:
    """Base processor for building artifact chunks from text content."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ) -> None:
        """Initialize the shared text splitter configuration."""
        if separators is None:
            separators = self._default_separators()

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
        )

    def _default_separators(self) -> list[str]:
        """Return default separators favoring markdown/text structure."""
        return [
            "\n\n## ",  # Major headings
            "\n\n### ",  # Subheadings
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence endings
            " ",  # Word boundaries
            "",  # Character boundaries
        ]

    def normalize_text(self, text: str) -> str:
        """Normalize and clean text."""
        text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines
        text = re.sub(r"[ \t]+", " ", text)  # Normalize spaces/tabs

        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)
        return text.strip()

    def split_text(self, text: str) -> list[str]:
        """Split normalized text into chunks."""
        normalized_text = self.normalize_text(text)
        return self.text_splitter.split_text(normalized_text)

    def _create_chunks_from_text_chunks(
        self,
        tenant_id: str,
        artifact_id: str,
        text_chunks: list[str],
        meta_data: dict[str, object] | None = None,
    ) -> list[ArtifactChunk]:
        """Build KnowledgeChunk objects from pre-split text chunks."""

        chunks: list[ArtifactChunk] = []
        for idx, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            chunks.append(
                ArtifactChunk(
                    tenant_id=tenant_id,
                    artifact_id=artifact_id,
                    chunk_index=idx,
                    text=chunk_text,
                    meta_data=meta_data.copy(),
                )
            )

        return chunks

    def _log_chunk_creation(self, count: int, artifact_id: str, tenant_id: str) -> None:
        """Log chunk creation results."""
        logger.info(
            "Created %d knowledge chunks for source %s (tenant: %s)",
            count,
            artifact_id,
            tenant_id,
        )

    async def create_chunks(
        self,
        tenant_id: str,
        text: str,
        artifact_id: str,
        meta_data: dict[str, object] | None = None,
    ) -> list[ArtifactChunk]:
        """Create KnowledgeChunk objects from raw text."""
        text_chunks = self.split_text(text)
        chunks = self._create_chunks_from_text_chunks(
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            text_chunks=text_chunks,
            meta_data=meta_data,
        )
        self._log_chunk_creation(len(chunks), artifact_id, tenant_id)
        chunks = await self.embed_chunks(chunks)
        for chunk in chunks:
            await chunk.save()
        return chunks

    async def embed_chunks(self, chunks: list[ArtifactChunk]) -> list[ArtifactChunk]:
        """Embed chunks."""
        embeddings, errors = await generate_embeddings_batch(chunks)
        if errors:
            logger.error("Failed to embed chunks: %s", errors)
            raise ValueError(f"Failed to embed chunks: {errors}")

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = embedding

        return chunks
