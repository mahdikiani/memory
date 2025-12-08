"""
Prompts package for the memory service.

Extract prompts from external sources.
- File system
- API
- Default prompts
"""

from .services import PromptService

__all__ = ["PromptService"]
