"""Embedding service for generating vector embeddings."""

import logging

from openai import OpenAI

from server.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using OpenRouter-compatible API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize embedding service.

        Args:
            settings: Application settings (defaults to Settings() if not provided)

        """
        if settings is None:
            settings = Settings()

        self.settings = settings
        self.client: OpenAI | None = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize OpenAI client configured for OpenRouter."""
        self.client = OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=self.settings.openrouter_base_url,
        )
        logger.info(
            "Initialized embedding service with model: %s",
            self.settings.embedding_model,
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of float values representing the embedding vector

        """
        if not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        try:
            response = self.client.embeddings.create(
                model=self.settings.embedding_model,
                input=text,
            )
            embedding = response.data[0].embedding
            logger.debug("Generated embedding of dimension %d", len(embedding))
        except Exception:
            logger.exception("Failed to generate embedding")
            raise

        return embedding

    async def generate_embeddings_batch(
        self, texts: list[str], batch_size: int = 100
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch

        Returns:
            List of embedding vectors (one per input text)

        """
        if not texts:
            return []

        # Filter out empty texts
        valid_texts = [text for text in texts if text.strip()]
        if len(valid_texts) != len(texts):
            logger.warning(
                "Filtered out %d empty texts from batch",
                len(texts) - len(valid_texts),
            )

        if not valid_texts:
            return []

        embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(valid_texts), batch_size):
            batch = valid_texts[i : i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=batch,
                )
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
