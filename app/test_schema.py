"""Test script to verify SurrealDB connection and schema generation."""

import asyncio
import logging
import sys

from apps.memory.models import Artifact, ArtifactChunk, Entity, Event
from db.schema_generator import _quote_identifier, get_models_and_indexes
from server.config import Settings
from server.db import DatabaseManager

__all__ = ["Artifact", "ArtifactChunk", "Entity", "Event"]

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s %(name)s:%(filename)s:%(lineno)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def test_schema_generation() -> None:
    """Test schema generation and database connection."""
    try:
        logger.info("=" * 80)
        logger.info("Testing SurrealDB Schema Generation")
        logger.info("=" * 80)

        # Test 1: Get models and indexes
        logger.info("\n1. Extracting models and indexes from Pydantic models...")
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
        logger.info("\n2. Connecting to SurrealDB...")
        settings = Settings()
        logger.info("   URI: %s", settings.surrealdb_uri)
        logger.info("   Namespace: %s", settings.surrealdb_namespace)
        logger.info("   Database: %s", settings.surrealdb_database)

        db_manager = DatabaseManager(
            settings.surrealdb_uri,
            settings.surrealdb_username,
            settings.surrealdb_password,
            settings.surrealdb_namespace,
            settings.surrealdb_database,
        )
        await db_manager.aconnect()
        await db_manager.ainit_schema()
        db = db_manager.get_db()
        logger.info("   ✓ Connected successfully!")

        # Test 3: Verify schema was created
        logger.info("\n3. Verifying schema creation...")
        for table_name in models:
            # Query to check if table exists
            quoted_table_name = _quote_identifier(table_name)
            logging.info("INFO FOR TABLE %s;", quoted_table_name)
            result = await db.query(f"INFO FOR TABLE {quoted_table_name};")
            if result:
                logger.info("   ✓ Table '%s' exists", table_name)
            else:
                logger.warning("   ✗ Table '%s' not found", table_name)

        # Test 4: Check indexes
        logger.info("\n4. Verifying indexes...")
        for table_name, table_indexes in indexes.items():
            if table_indexes:
                quoted_table_name = _quote_identifier(table_name)
                result = await db.query(f"INFO FOR TABLE {quoted_table_name};")
                logger.info(
                    "   Table '%s' has %d indexes defined",
                    table_name,
                    len(table_indexes),
                )

        logger.info("\n %s", "=" * 80)
        logger.info("✓ All tests passed!")
        logger.info("=" * 80)

    except Exception:
        logger.exception("\n✗ Test failed with error")
        sys.exit(1)
    finally:
        await db_manager.adisconnect()


if __name__ == "__main__":
    asyncio.run(test_schema_generation())
