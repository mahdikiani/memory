"""Service for managing tenant-specific configurations."""

import logging

from apps.knowledge.schemas import TenantConfig
from server.db import db_manager

logger = logging.getLogger(__name__)

# Default allowed source types (fallback)
DEFAULT_ALLOWED_SOURCE_TYPES = [
    "document",
    "meeting",
    "calendar",
    "task",
    "crm",
    "chat",
]

# In-memory cache for tenant configs (populated async, accessed sync)
_tenant_config_cache: dict[str, TenantConfig] = {}


def _get_cached_tenant_config(tenant_id: str) -> TenantConfig | None:
    """Get tenant config from in-memory cache (synchronous)."""
    return _tenant_config_cache.get(tenant_id)


def _set_cached_tenant_config(tenant_id: str, config: TenantConfig) -> None:
    """Set tenant config in in-memory cache (synchronous)."""
    _tenant_config_cache[tenant_id] = config


def _clear_tenant_config_cache(tenant_id: str | None = None) -> None:
    """Clear tenant config cache."""
    if tenant_id:
        _tenant_config_cache.pop(tenant_id, None)
    else:
        _tenant_config_cache.clear()


async def load_tenant_config(tenant_id: str) -> TenantConfig:
    """
    Load tenant configuration from database (async).

    This should be called during application startup or when config changes.
    """
    try:
        db = db_manager.get_db()
        result = await db.select(f"tenant_config:{tenant_id}")
        if result:
            config = TenantConfig(**result)
            _set_cached_tenant_config(tenant_id, config)
            return config
    except Exception as e:
        logger.warning(
            "Failed to load tenant config for %s: %s. Using defaults.", tenant_id, e
        )

    # Return default config if not found
    config = TenantConfig(
        tenant_id=tenant_id,
        allowed_source_types=DEFAULT_ALLOWED_SOURCE_TYPES,
    )
    _set_cached_tenant_config(tenant_id, config)
    return config


def get_tenant_config(tenant_id: str) -> TenantConfig | None:
    """
    Get tenant configuration from cache (synchronous).

    For use in Pydantic validators. Returns None if not cached.
    Call load_tenant_config() first to populate cache.
    """
    return _get_cached_tenant_config(tenant_id)


async def get_tenant_config_async(tenant_id: str) -> TenantConfig:
    """
    Get tenant configuration asynchronously (bypasses cache).

    Use this when you need fresh data or are in an async context.
    """
    try:
        db = db_manager.get_db()
        result = await db.select(f"tenant_config:{tenant_id}")
        if result:
            return TenantConfig(**result)
    except Exception as e:
        logger.warning(
            "Failed to load tenant config for %s: %s. Using defaults.", tenant_id, e
        )

    # Return default config if not found
    return TenantConfig(
        tenant_id=tenant_id,
        source_types=DEFAULT_ALLOWED_SOURCE_TYPES,
    )


def get_tenant_source_types(tenant_id: str) -> list[str]:
    """
    Get allowed source types for a tenant (synchronous, uses cache).

    This is used by Pydantic validators which need synchronous access.
    Falls back to defaults if config not found in cache.
    """
    config = get_tenant_config(tenant_id)
    if config:
        return config.source_types
    # Fallback to defaults if not in cache
    return DEFAULT_ALLOWED_SOURCE_TYPES


async def get_tenant_source_types_async(tenant_id: str) -> list[str]:
    """Get allowed source types for a tenant (async, fresh data)."""
    config = await get_tenant_config_async(tenant_id)
    return config.source_types


def get_tenant_entity_types(tenant_id: str) -> list[str] | None:
    """
    Get allowed entity types for a tenant (synchronous, uses cache).

    Returns None if all entity types are allowed.
    """
    config = get_tenant_config(tenant_id)
    if config:
        return config.entity_types
    return None


async def get_tenant_entity_types_async(tenant_id: str) -> list[str] | None:
    """Get allowed entity types for a tenant (async, fresh data)."""
    config = await get_tenant_config_async(tenant_id)
    return config.entity_types


def get_tenant_relation_types(tenant_id: str) -> list[str] | None:
    """
    Get allowed relation types for a tenant (synchronous, uses cache).

    Returns None if all relation types are allowed.
    """
    config = get_tenant_config(tenant_id)
    if config:
        return config.relation_types
    return None


async def get_tenant_relation_types_async(tenant_id: str) -> list[str] | None:
    """Get allowed relation types for a tenant (async, fresh data)."""
    config = await get_tenant_config_async(tenant_id)
    return config.relation_types


async def create_or_update_tenant_config(
    tenant_id: str,
    source_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    relation_types: list[str] | None = None,
) -> TenantConfig:
    """Create or update tenant configuration."""
    db = db_manager.get_db()

    # Get existing config or create new
    existing = await db.select(f"tenant_config:{tenant_id}")
    if existing:
        config = TenantConfig(**existing)
        if source_types is not None:
            config.source_types = source_types
        if entity_types is not None:
            config.entity_types = entity_types
        if relation_types is not None:
            config.relation_types = relation_types
    else:
        config = TenantConfig(
            tenant_id=tenant_id,
            source_types=source_types or DEFAULT_ALLOWED_SOURCE_TYPES,
            entity_types=entity_types,
            relation_types=relation_types,
        )

    # Save to database
    result = await db.create(
        f"tenant_config:{tenant_id}", config.model_dump(exclude={"id"})
    )

    # Update cache
    updated_config = TenantConfig(**result)
    _set_cached_tenant_config(tenant_id, updated_config)

    return updated_config
