"""FastAPI server for the memory service."""

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi_mongo_base.core import app_factory

from apps.memory.models import Entity, KnowledgeChunk, KnowledgeSource, Relation
from apps.memory.routes import router as memory_router

from . import config, db

__all__ = ["Entity", "KnowledgeChunk", "KnowledgeSource", "Relation"]


async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler."""
    logging.info("Lifespan started - initializing database connection")
    db_manager = db.DatabaseManager(config.Settings())
    await db_manager.connect()
    await db_manager.init_schema()
    db_manager.get_db()
    logging.info("Database connection initialized and schema created")
    yield
    await db_manager.disconnect()
    logging.info("Lifespan ended - database connection closed")


app = app_factory.create_app(settings=config.Settings(), lifespan_func=lifespan)
server_router = APIRouter()

for router in [memory_router]:
    server_router.include_router(router)

app.include_router(server_router, prefix=config.Settings.base_path)
