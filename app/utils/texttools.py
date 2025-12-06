"""Text tools for the memory service."""

import re


def camel_to_kebab(name: str) -> str:
    """Convert CamelCase or camelCase to kebab-case."""
    # Insert hyphen before any capital letter preceded by a lowercase or number
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    # Insert hyphen before contiguous capitals (for acronyms) like HTTPServer
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z0-9])", r"\1-\2", s1)
    return s2.lower()
