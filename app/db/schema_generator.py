"""Generate SurrealDB schema definitions from Pydantic models."""

import inspect
import logging
from datetime import datetime
from types import UnionType
from typing import Union, get_args, get_origin

import surrealdb
from pydantic import BaseModel

from .metadata import _get_table_name
from .utils import get_all_subclasses

AsyncSurrealConnection = (
    surrealdb.AsyncEmbeddedSurrealConnection
    | surrealdb.AsyncWsSurrealConnection
    | surrealdb.AsyncHttpSurrealConnection
)

logger = logging.getLogger(__name__)

# Cache for model-to-table mapping
_MODEL_TABLE_MAP: dict[str, str] | None = None


def _get_model_table_map() -> dict[str, str]:
    """Get mapping of model class names to table names."""
    global _MODEL_TABLE_MAP
    if _MODEL_TABLE_MAP is not None:
        return _MODEL_TABLE_MAP

    from .models import BaseSurrealEntity

    model_classes = get_all_subclasses(BaseSurrealEntity)
    _MODEL_TABLE_MAP = {
        model.__name__: _get_table_name(model) for model in model_classes
    }
    return _MODEL_TABLE_MAP


def _infer_table_name_from_field(field_name: str) -> str | None:
    """Infer table name from field name pattern."""
    model_map = _get_model_table_map()
    field_lower = field_name.lower()

    # Try to match field pattern to model/table names
    # e.g., "source_id" -> "KnowledgeSource" -> "knowledge-source"
    # e.g., "entity_id" -> "Entity" -> "entity"

    # Check for "source" pattern - look for models with "Source" in name
    if "source" in field_lower:
        for model_name, table_name in model_map.items():
            if "Source" in model_name and "Knowledge" in model_name:
                return table_name

    # Check for "entity" pattern - exact match for Entity model
    if "entity" in field_lower:
        for model_name, table_name in model_map.items():
            if model_name == "Entity":
                return table_name

    return None


def _quote_identifier(identifier: str) -> str:
    """Quote identifier if it contains special characters (hyphens, etc.)."""
    if "-" in identifier or " " in identifier or identifier[0].isdigit():
        return f"`{identifier}`"
    return identifier


def _handle_union_type(
    field_type: type, field_name: str, table_name: str | None
) -> str | None:
    """Handle Union types (X | Y or Union[X, Y]). Returns None if not a union."""
    origin = get_origin(field_type)
    args = get_args(field_type)

    is_union = (
        origin is Union
        or (
            hasattr(UnionType, "__instancecheck__")
            and isinstance(field_type, UnionType)
        )
        or str(type(field_type)) == "<class 'types.UnionType'>"
    )

    if not is_union or not args:
        return None

    non_none_args = [a for a in args if a is not type(None)]
    if len(non_none_args) == 1:
        inner = python_type_to_surreal_type(non_none_args[0], field_name, table_name)
        return f"option<{inner}>"
    elif len(non_none_args) > 1:
        return python_type_to_surreal_type(non_none_args[0], field_name, table_name)
    return None


def _handle_list_type(
    field_type: type, field_name: str, table_name: str | None
) -> str | None:
    """Handle list/array types. Returns None if not a list."""
    origin = get_origin(field_type)
    args = get_args(field_type)

    if origin is not list or not args:
        return "array" if origin is list else None

    inner_type = args[0]
    if inner_type is float:
        return "array<float>"
    if inner_type is str:
        if field_name.endswith(("_ids", "_id")):
            inferred_table = _infer_table_name_from_field(field_name)
            if inferred_table:
                quoted_table = _quote_identifier(inferred_table)
                return f"array<record<{quoted_table}>>"
        return "array<string>"

    inner_surreal = python_type_to_surreal_type(inner_type, field_name, table_name)
    return f"array<{inner_surreal}>"


def _handle_string_type(field_name: str, table_name: str | None) -> str:
    """Handle string type with record reference inference."""
    if not (field_name.endswith("_id") and field_name not in ("id", "tenant_id")):
        return "string"

    # Special cases: source_id in KnowledgeSource and IngestJob are external IDs
    model_map = _get_model_table_map()
    if field_name == "source_id" and table_name:
        # Check if current table is KnowledgeSource or IngestJob
        for model_name, table in model_map.items():
            if table == table_name and model_name in ("KnowledgeSource", "IngestJob"):
                return "string"

    # Infer table name from field name
    inferred_table = _infer_table_name_from_field(field_name)
    if inferred_table:
        quoted_table = _quote_identifier(inferred_table)
        return f"record<{quoted_table}>"
    return "string"


def _handle_basic_type(field_type: type) -> str | None:
    """Handle basic Python types. Returns None if not a basic type."""
    if field_type is int:
        return "int"
    if field_type is float:
        return "float"
    if field_type is bool:
        return "bool"
    if field_type is datetime or (
        inspect.isclass(field_type) and issubclass(field_type, datetime)
    ):
        return "datetime"
    return None


def python_type_to_surreal_type(
    field_type: type, field_name: str, table_name: str | None = None
) -> str:
    """Convert Python type to SurrealDB type string."""
    origin = get_origin(field_type)

    # Handle Union types
    union_result = _handle_union_type(field_type, field_name, table_name)
    if union_result is not None:
        return union_result

    # Handle list/array types
    list_result = _handle_list_type(field_type, field_name, table_name)
    if list_result is not None:
        return list_result

    # Handle dict/object types
    if origin is dict:
        return "object"

    # Handle string types
    if field_type is str:
        return _handle_string_type(field_name, table_name)

    # Handle basic types
    basic_result = _handle_basic_type(field_type)
    if basic_result is not None:
        return basic_result

    # Default fallback
    return "string"


def get_all_fields(model: type[BaseModel]) -> dict[str, object]:
    """Get all fields from a model including inherited fields."""
    fields = {}

    # Walk through MRO to get all fields
    for base in inspect.getmro(model):
        if issubclass(base, BaseModel) and hasattr(base, "model_fields"):
            for field_name, field_info in base.model_fields.items():
                if field_name not in fields:
                    fields[field_name] = field_info

    return fields


def generate_table_schema(
    model: type[BaseModel], table_name: str, indexes: dict[str, list[str]] | None = None
) -> str:
    """Generate SurrealDB table schema definition from a Pydantic model."""
    quoted_table = _quote_identifier(table_name)
    lines = [f"DEFINE TABLE {quoted_table} SCHEMAFULL;"]

    fields = get_all_fields(model)

    for field_name, field_info in fields.items():
        field_type = field_info.annotation

        # Skip if field_type is not available
        if field_type is None:
            continue

        surreal_type = python_type_to_surreal_type(field_type, field_name, table_name)

        # Handle special case for id field
        if field_name == "id":
            surreal_type = f"record<{quoted_table}>"

        # Build field definition
        quoted_field = _quote_identifier(field_name)
        field_def = f"DEFINE FIELD {quoted_field} ON {quoted_table} TYPE {surreal_type}"

        # Add default for datetime fields
        if field_name in ("created_at", "updated_at"):
            field_def += " DEFAULT time::now()"

        lines.append(field_def + ";")

    # Add indexes
    if indexes:
        for index_name, index_fields in indexes.items():
            quoted_index = _quote_identifier(index_name)
            quoted_fields = ", ".join(_quote_identifier(f) for f in index_fields)
            lines.append(
                f"DEFINE INDEX {quoted_index} ON {quoted_table} FIELDS {quoted_fields};"
            )

    return "\n        ".join(lines)


def generate_schema_init_function(
    models: dict[str, type[BaseModel]],
    indexes: dict[str, dict[str, list[str]]] | None = None,
) -> str:
    """Generate the init_schema function code."""
    if indexes is None:
        indexes = {}

    lines = [
        "async def init_schema() -> None:",
        '    """Initialize SurrealDB schema with all required tables and indexes."""',
        "    surreal_db = db_manager.get_db()",
        "",
    ]

    for table_name, model in models.items():
        table_indexes = indexes.get(table_name, {})
        schema = generate_table_schema(model, table_name, table_indexes)

        lines.append(f"    # Define {table_name} table")
        lines.append("    await surreal_db.query(")
        lines.append('        """')
        lines.append(f"        {schema}")
        lines.append('        """')
        lines.append("    )")
        lines.append("")

    lines.append('    logger.info("SurrealDB schema initialized successfully")')

    return "\n".join(lines)


def extract_indexes_from_model(model: type[BaseModel]) -> dict[str, list[str]]:
    """Extract index definitions from model fields using Field metadata."""
    fields = get_all_fields(model)

    # Get field order from model (preserves definition order)
    field_order = (
        list(model.model_fields.keys()) if hasattr(model, "model_fields") else []
    )

    # Group fields by index name, preserving order
    index_fields: dict[str, list[str]] = {}
    for field_name in field_order:
        if field_name not in fields:
            continue
        field_info = fields[field_name]
        # Get json_schema_extra if it exists
        json_schema_extra = getattr(field_info, "json_schema_extra", None)
        if json_schema_extra and isinstance(json_schema_extra, dict):
            index_name = json_schema_extra.get("surreal_index")
            if index_name:
                if index_name not in index_fields:
                    index_fields[index_name] = []
                # Only add if not already present (to preserve order)
                if field_name not in index_fields[index_name]:
                    index_fields[index_name].append(field_name)

    return index_fields


def get_models_and_indexes() -> tuple[
    dict[str, type[BaseModel]], dict[str, dict[str, list[str]]]
]:
    """Get models and indexes configuration dynamically from Field metadata."""
    from .models import BaseSurrealEntity

    model_classes = get_all_subclasses(BaseSurrealEntity)
    # Use table names as keys instead of model class names
    models = {_get_table_name(model): model for model in model_classes}

    # Extract indexes dynamically from each model
    indexes = {}
    for table_name, model in models.items():
        indexes[table_name] = extract_indexes_from_model(model)

    return models, indexes


async def init_schema(surreal_db: AsyncSurrealConnection) -> None:
    """Initialize SurrealDB schema with all required tables and indexes."""
    models, indexes = get_models_and_indexes()

    for table_name, model in models.items():
        table_indexes = indexes.get(table_name, {})
        schema = generate_table_schema(model, table_name, table_indexes)

        logger.debug("Defining table: %s", table_name)
        await surreal_db.query(schema)

    # Define custom functions
    await _define_custom_functions(surreal_db)

    logger.info("SurrealDB schema initialized successfully")


async def _define_custom_functions(surreal_db: AsyncSurrealConnection) -> None:
    """Define custom SurrealDB functions."""
    return
    import logging
    from pathlib import Path

    import aiofiles

    logger = logging.getLogger(__name__)

    # Define cosine similarity function
    async with aiofiles.open(
        Path(__file__).parent / "surreal_files" / "cossine_function.surql"
    ) as f:
        cosine_similarity_function = await f.read()

    logger.debug("Defining cosine_similarity function")
    await surreal_db.query(cosine_similarity_function)
    logger.info("Custom functions defined successfully")


def generate_schemas_file() -> str:
    """Generate the complete schemas.py file content."""
    models, indexes = get_models_and_indexes()

    header = '''"""SurrealDB schema initialization and table definitions."""

import logging

from server.db import db_manager

logger = logging.getLogger(__name__)


'''

    init_function = generate_schema_init_function(models, indexes)

    return header + init_function
