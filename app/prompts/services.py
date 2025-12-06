"""Prompt service for loading prompts from external sources."""

import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from singleton import Singleton

from server.config import Settings

from .schemas import PromptSchema

logger = logging.getLogger(__name__)


class PrompticClient(httpx.AsyncClient):
    """Client for Promptic API."""

    def __init__(self, base_url: str) -> None:
        """Initialize Promptic client."""
        super().__init__(base_url=base_url, timeout=10.0)

    async def get_prompt(self, prompt_name: str) -> PromptSchema:
        """Get a prompt by name and return a PromptSchema."""
        response = await self.get(f"/prompts/{prompt_name}")
        response.raise_for_status()
        return PromptSchema.model_validate(response.json())


class PromptService(metaclass=Singleton):
    """Service for loading and managing prompts from external sources."""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize prompt service.

        Args:
            settings: Application settings (defaults to Settings() if not provided)

        """
        if settings is None:
            settings = Settings()

        self.settings = settings
        self._prompt_cache: dict[str, dict[str, str]] = {}
        self._prompt_source: str | None = (
            getattr(settings, "prompt_source", None) or None
        )
        self._prompts_dir: Path = self.settings.base_dir / "prompts"

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL."""
        try:
            result = urlparse(source)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    async def _load_prompt_from_file(self, prompt_name: str) -> dict[str, str] | None:
        """
        Load a single prompt from its own file.

        Args:
            prompt_name: Name of the prompt (e.g., "entity_extraction")

        Returns:
            Dictionary with "system" and "user" keys, or None if not found

        """
        parsers = {
            ".yaml": yaml.safe_load,
            ".yml": yaml.safe_load,
            ".json": json.loads,
            ".txt": lambda x: {"system": x, "user": "{text}"},
            ".md": lambda x: {"system": x, "user": "{text}"},
            ".prompt": lambda x: {"system": x, "user": "{text}"},
        }
        # Try different file extensions
        for ext, parser in parsers.items():
            prompt_file = self._prompts_dir / f"{prompt_name}{ext}"
            if not prompt_file.exists():
                continue

            try:
                file_content = prompt_file.read_text(encoding="utf-8")
                content = parser(file_content)
                if (
                    content
                    and isinstance(content, dict)
                    and "system" in content
                    and "user" in content
                ):
                    return content
            except Exception as e:
                logger.warning("Failed to load prompt file %s: %s", prompt_file, e)
                continue

        return None

    async def _load_prompt_from_api(self, prompt_name: str) -> dict[str, str] | None:
        """
        Load a single prompt from API endpoint.

        Args:
            prompt_name: Name of the prompt

        Returns:
            Dictionary with "system" and "user" keys, or None if not found

        """
        # Construct API URL: {base_url}/{prompt_name}
        base = self._prompt_source.rstrip("/")
        try:
            async with PrompticClient(base_url=base) as client:
                await client.get_prompt(prompt_name)
                return {}
        except Exception as e:
            logger.warning("Failed to load prompt from API %s: %s", base, e)
            return None

    async def get_prompt(
        self, prompt_name: str, use_cache: bool = True
    ) -> dict[str, str]:
        """
        Get a prompt by name.

        Args:
            prompt_name: Name of the prompt (e.g., "entity_extraction")
            use_cache: Whether to use cached prompts

        Returns:
            Dictionary with "system" and "human" prompt templates

        """
        # Check cache first
        if use_cache and prompt_name in self._prompt_cache:
            return self._prompt_cache[prompt_name]

        # Try to load from external source
        prompt: dict[str, str] | None = None

        if self._prompts_dir:
            # Load from file system
            prompt = await self._load_prompt_from_file(prompt_name, self._prompts_dir)
        elif self._prompt_source and self._is_url(self._prompt_source):
            # Load from API
            prompt = await self._load_prompt_from_api(prompt_name, self._prompt_source)

        if prompt:
            self._prompt_cache[prompt_name] = prompt
            logger.debug("Loaded prompt '%s' from external source", prompt_name)
            return prompt

        msg = f"Prompt '{prompt_name}' not found in defaults or external source"
        raise ValueError(msg)

    async def reload_prompts(self) -> None:
        """Reload prompts from external source and clear cache."""
        self._prompt_cache.clear()
        logger.info("Prompt cache cleared, will reload on next request")

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._prompt_cache.clear()
        logger.debug("Prompt cache cleared")
