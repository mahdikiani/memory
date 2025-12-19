"""Text tools for the memory service."""

import re


def camel_to_kebab(name: str) -> str:
    """Convert CamelCase or camelCase to kebab-case."""
    # Insert hyphen before any capital letter preceded by a lowercase or number
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    # Insert hyphen before contiguous capitals (for acronyms) like HTTPServer
    s2 = re.sub(r"([A-Z]+)([A-Z][a-z0-9])", r"\1-\2", s1)
    return s2.lower()


def camel_to_snake(name: str) -> str:
    """Convert CamelCase or camelCase to snake_case."""
    # Insert underscore before any capital letter preceded by a lowercase or number
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def kebab_to_snake(name: str) -> str:
    """Convert kebab-case to snake_case."""
    return name.replace("-", "_")


def snake_to_camel(name: str) -> str:
    """Convert snake_case to CamelCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def snake_to_kebab(name: str) -> str:
    """Convert snake_case to kebab-case."""
    return "-".join(word for word in name.split("_"))


def kebab_to_camel(name: str) -> str:
    """Convert kebab-case to CamelCase."""
    return "".join(word.capitalize() for word in name.split("-"))
