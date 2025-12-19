"""Test script to verify SurrealDB connection and schema generation."""

import asyncio
import logging

from apps.memory.models import Entity
from db.schema_generator import get_models_and_indexes, init_schema
from server.config import Settings
from server.db import db_manager

settings = Settings()
settings.config_logger()

logger = logging.getLogger(__name__)


async def test_schema() -> None:
    """Test schema generation and database connection."""
    try:
        logger.info("=" * 80)
        logger.info("Testing SurrealDB Schema Generation")
        logger.info("=" * 80)

        # Test 1: Get models and indexes
        logger.info("1. Extracting models and indexes from Pydantic models...")
        models, indexes = get_models_and_indexes()

        logger.info("   Found %d models:", len(models))
        for table_name, model in models.items():
            logger.info("     - %s (%s)", table_name, model.__name__)

        logger.info("\n   Found indexes for %d tables:", len(indexes))
        for table_name, table_indexes in indexes.items():
            logger.info("     - %s:", table_name)
            for idx_name, fields in table_indexes.items():
                logger.info("       • %s: %s", idx_name, fields)

        # Test 2: Connect to database
        logger.info("2. Connecting to SurrealDB...")
        db_manager.surrealdb_uri = "wss://surreal.uln.me/rpc"
        await db_manager.aconnect()
        await db_manager.ainit_schema()
        db = db_manager.get_db()
        logger.info("   ✓ Connected successfully!")

        # Test 3: Create a new entity
        logger.info("3. Creating a new company...")
        company = Entity(entity_type="c1", name="Company 1")
        await company.save()
        logger.info(
            "   ✓ Company created successfully! ID: %s %s", type(company.id), company.id
        )

        logger.info("\n4. Creating a new company entity...")
        entity = Entity(entity_type="person", name="John Doe")
        await entity.save()
        logger.info("   ✓ Entity created successfully! ID: %s", entity.id)

        # Test 4: Query the entity
        logger.info("5. Querying the entity...")
        results = await Entity.find_many(entity_type="person")
        logger.info("   ✓ Query results: %s", results)

        logger.info("6. Testing schema generation...")
        await init_schema(db)
        logger.info("   ✓ Schema generation completed successfully!")

        logger.info("7. Testing database connection...")
        await db.close()
        logger.info("   ✓ Database connection closed successfully!")

    except Exception as e:
        logger.exception("Test failed")
        logger.info("Test failed %s: %s", type(e), e)
        # sys.exit(1)

    finally:
        logger.info("Test completed")
        logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_schema())
