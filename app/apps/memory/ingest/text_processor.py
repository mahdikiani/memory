"""Text processing service for knowledge chunks."""

import logging
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..models import KnowledgeChunk

logger = logging.getLogger(__name__)


class TextProcessor:
    """Service for processing and chunking text content."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ) -> None:
        """
        Initialize text processor.

        Args:
            chunk_size: Maximum size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            separators: Custom separators for text splitting (default: markdown-aware)

        """
        if separators is None:
            # Markdown-aware separators: prioritize semantic boundaries
            separators = [
                "\n\n## ",  # Major headings
                "\n\n### ",  # Subheadings
                "\n\n",  # Paragraph breaks
                "\n",  # Line breaks
                ". ",  # Sentence endings
                " ",  # Word boundaries
                "",  # Character boundaries
            ]

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
            length_function=len,
            is_separator_regex=False,
        )

    def normalize_text(self, text: str) -> str:
        """
        Normalize and clean markdown text.

        Args:
            text: Raw markdown text

        Returns:
            Normalized markdown text

        """
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines
        text = re.sub(r"[ \t]+", " ", text)  # Normalize spaces/tabs

        # Remove trailing whitespace from lines
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def split_text(self, text: str) -> list[str]:
        """
        Split text into chunks using LangChain's recursive text splitter.

        Args:
            text: Text to split

        Returns:
            List of text chunks

        """
        normalized_text = self.normalize_text(text)
        chunks = self.text_splitter.split_text(normalized_text)
        logger.debug("Split text into %d chunks", len(chunks))
        return chunks

    def create_chunks(
        self,
        tenant_id: str,
        text: str,
        source_id: str,
        metadata: dict[str, object] | None = None,
    ) -> list[KnowledgeChunk]:
        """
        Create KnowledgeChunk objects from text.

        Args:
            tenant_id: Tenant ID
            text: Text content to chunk
            source_id: ID of the knowledge source
            metadata: Additional metadata to attach to chunks

        Returns:
            List of KnowledgeChunk objects

        """
        if metadata is None:
            metadata = {}

        text_chunks = self.split_text(text)
        knowledge_chunks: list[KnowledgeChunk] = []

        for idx, chunk_text in enumerate(text_chunks):
            # Skip empty chunks
            if not chunk_text.strip():
                continue

            chunk = KnowledgeChunk(
                tenant_id=tenant_id,
                source_id=source_id,
                chunk_index=idx,
                text=chunk_text,
                metadata=metadata.copy(),  # Copy to avoid shared references
            )
            knowledge_chunks.append(chunk)

        logger.info(
            "Created %d knowledge chunks for source %s (tenant: %s)",
            len(knowledge_chunks),
            source_id,
            tenant_id,
        )

        return knowledge_chunks
