"""Field name validation and sanitization for safe queries."""

import logging
import re

from .metadata import _get_allowed_fields

logger = logging.getLogger(__name__)


def validate_field_name(field: str) -> bool:
    """
    Validate that a field name is safe to use in queries.

    Uses dynamic discovery from Pydantic models + pattern-based fallback.

    Args:
        field: Field name to validate

    Returns:
        True if field is safe, False otherwise

    """
    # First check dynamic whitelist from models
    allowed_fields = _get_allowed_fields()
    if field in allowed_fields:
        return True

    # Fallback: Allow field names that match identifier pattern
    # (alphanumeric + underscore, starting with letter/underscore)
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field):
        logger.warning(
            "Field '%s' not found in model fields, but matches safe pattern", field
        )
        return True

    logger.error("Unsafe field name detected: %s", field)
    return False


def sanitize_field_name(field: str) -> str:
    """
    Sanitize field name for use in queries.

    Args:
        field: Field name to sanitize

    Returns:
        Sanitized field name

    """
    if not validate_field_name(field):
        raise ValueError(f"Unsafe field name: {field}")

    # Escape backticks if used
    return field.replace("`", "``")
