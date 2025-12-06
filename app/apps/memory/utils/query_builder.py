"""Safe query builder for SurrealDB to prevent SQL injection."""

import logging
import re

logger = logging.getLogger(__name__)

# Whitelist of allowed field names to prevent injection through field names
ALLOWED_FIELDS = {
    "tenant_id",
    "is_deleted",
    "source_id",
    "source_type",
    "sensor_name",
    "entity_type",
    "name",
    "relation_type",
    "from_entity_id",
    "to_entity_id",
    "chunk_index",
    "text",
    "embedding",
}


def validate_field_name(field: str) -> bool:
    """
    Validate that a field name is safe to use in queries.

    Args:
        field: Field name to validate

    Returns:
        True if field is safe, False otherwise

    """
    # Check if field is in whitelist
    if field in ALLOWED_FIELDS:
        return True

    # Allow field names that match identifier pattern (alphanumeric + underscore)
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", field):
        logger.warning("Field '%s' not in whitelist, but matches safe pattern", field)
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
