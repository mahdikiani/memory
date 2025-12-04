"""
Legacy models module - re-exports from new structure.

This file exists for backward compatibility.
New code should import directly from apps.knowledge.models.
"""

# Import all models from the models subdirectory
from .models import (  # noqa: F401
    ChunkResponse,
    ContextResponse,
    Entity,
    EntityResponse,
    IngestRequest,
    IngestResponse,
    JobStatusResponse,
    KnowledgeChunk,
    KnowledgeSource,
    Relation,
    RetrieveRequest,
    RetrieveResponse,
)
