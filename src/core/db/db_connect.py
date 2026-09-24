# Copyright (c) 2026 Indus Net Technologies
# Licensed under the Business Source License 1.1 (BUSL-1.1)
# See LICENSE file in the project root for full licence terms.
# Additional Use Grant: internal deployment and modification only.
# Commercial licensing: licensing@intglobal.com
"""MongoDB connection lifecycle and Beanie initialization.

Beanie 2.x uses PyMongo's native async driver (``AsyncMongoClient``); Motor is
no longer involved.
"""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from src.core.config import Settings
from src.core.db.db_schema import DOCUMENT_MODELS
from src.core.logging.logger import get_logger

logger = get_logger(__name__)


class MongoDB:
    """Holds the async client and database handle for the app lifetime."""

    client: AsyncMongoClient | None = None
    database: AsyncDatabase | None = None


db = MongoDB()


async def connect_to_mongo(settings: Settings) -> None:
    """Open the async client and bind Beanie to the document models."""
    from beanie import init_beanie

    logger.info("Connecting to MongoDB ....")
    db.client = AsyncMongoClient(settings.mongodb_uri)
    db.database = db.client[settings.mongodb_db]
    await init_beanie(database=db.database, document_models=DOCUMENT_MODELS)
    logger.info("MongoDB connected, Beanie initialized (db=%s)", settings.mongodb_db)


async def close_mongo_connection() -> None:
    """Close the async client."""
    if db.client is not None:
        await db.client.close()
        db.client = None
        db.database = None
        logger.info("MongoDB connection closed")


async def ping_db() -> None:
    """Round-trip MongoDB. Raises if the client was never built or the server
    does not answer. Used by the /health probe, which turns the error into text."""
    if db.client is None:
        raise RuntimeError("MongoDB client not initialised")
    await db.client.admin.command("ping")
