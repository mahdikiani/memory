"""Metadata extraction helpers for dynamic model discovery."""

import inspect

from pydantic import BaseModel

from .utils import camel_to_kebab, get_all_subclasses

# Cache for dynamically discovered field names
_ALLOWED_FIELDS: set[str] | None = None


def _get_table_name(model: type[BaseModel]) -> str:
    """Get the table name for a model."""

    return camel_to_kebab(model.__name__)


def _get_vector_field(model: type[BaseModel]) -> str | None:
    """Get the vector field name from model metadata."""
    if not hasattr(model, "model_fields"):
        return None
    for field_name, field_info in model.model_fields.items():
        if field_info.json_schema_extra and field_info.json_schema_extra.get(
            "surreal_vector_field"
        ):
            return field_name
    return None


def _get_fulltext_field(model: type[BaseModel]) -> str | None:
    """Get the fulltext field name from model metadata."""
    if not hasattr(model, "model_fields"):
        return None
    for field_name, field_info in model.model_fields.items():
        if field_info.json_schema_extra and field_info.json_schema_extra.get(
            "surreal_fulltext_field"
        ):
            return field_name
    return None


def _model_classes() -> list[type[BaseModel]]:
    """Get all model classes from BaseSurrealEntity."""
    from .models import BaseSurrealEntity

    return get_all_subclasses(BaseSurrealEntity)


def _get_graph_node_model() -> type[BaseModel] | None:
    """Get the model marked as graph node from metadata."""
    for model_class in _model_classes():
        if hasattr(model_class, "model_config"):
            config = model_class.model_config
            if config.get("json_schema_extra", {}).get("surreal_graph_node"):
                return model_class
    return None


def _get_graph_edge_model() -> type[BaseModel] | None:
    """Get the model marked as graph edge from metadata."""

    for model_class in _model_classes():
        if hasattr(model_class, "model_config"):
            config = model_class.model_config
            if config.get("json_schema_extra", {}).get("surreal_graph_edge"):
                return model_class
    return None


def _get_allowed_fields() -> set[str]:
    """Dynamically get all field names from BaseSurrealTenantEntity models."""
    global _ALLOWED_FIELDS

    if _ALLOWED_FIELDS is not None:
        return _ALLOWED_FIELDS

    # Collect all field names from all models
    allowed_fields: set[str] = set()

    for model_class in _model_classes():
        # Walk through MRO to get all fields (including inherited)
        for base in inspect.getmro(model_class):
            if issubclass(base, BaseModel) and hasattr(base, "model_fields"):
                for field_name in base.model_fields:
                    allowed_fields.add(field_name)

    _ALLOWED_FIELDS = allowed_fields
    return allowed_fields
