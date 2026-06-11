"""MongoDB connection lifecycle and Beanie initialization.

Beanie 2.x uses PyMongo's native async driver (``AsyncMongoClient``); Motor is
no longer involved.
"""

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schedule import DOCUMENT_MODELS

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


async def ping() -> bool:
    """Return True if the database responds to a ping, False on any error."""
    if db.client is None:
        return False
    try:
        await db.client.admin.command("ping")
    except Exception:
        return False
    return True
