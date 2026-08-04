from pymongo import AsyncMongoClient
from beanie import init_beanie
from src.core.config import settings
from src.core.db.db_schemas import (
    APIKey,
    Assistant,
    AudioAsset,
    OutboundSIP,
    InboundSIP,
    InboundContextStrategy,
    CallRecord,
    OutboundCallQueue,
    Tool,
    ActivityLog,
    UsageRecord,
)
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database connection manager for MongoDB with Beanie"""

    client: AsyncMongoClient = None

    @classmethod
    async def connect_db(cls):
        """Initialize database connection and Beanie ODM.

        No-op if already connected — every LiveKit job calls this at the top of
        entrypoint(), and re-doing the ping + init_beanie() (11 document models) on an
        already-live client just adds latency for no benefit.
        """
        if cls.client is not None:
            return
        try:
            cls.client = AsyncMongoClient(settings.MONGODB_URL, tz_aware=True)

            # Test connection
            await cls.client.admin.command("ping")
            logger.info(f"Successfully connected to MongoDB at {settings.MONGODB_URL}")

            # Initialize Beanie with document models
            await init_beanie(
                database=cls.client[settings.DATABASE_NAME],
                document_models=[
                    APIKey,
                    Assistant,
                    AudioAsset,
                    OutboundSIP,
                    InboundSIP,
                    InboundContextStrategy,
                    CallRecord,
                    OutboundCallQueue,
                    Tool,
                    ActivityLog,
                    UsageRecord,
                ],
            )
            logger.info(f"Beanie initialized with database: {settings.DATABASE_NAME}")

        except Exception as e:
            cls.client = None  # don't leave a broken client behind — next call must retry, not no-op
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def close_db(cls):
        """Close database connection"""
        if cls.client:
            await cls.client.close()
            cls.client = None  # let a later connect_db() reconnect instead of no-op'ing
            logger.info("MongoDB connection closed")


# Convenience functions for FastAPI lifespan events
async def init_db():
    """Initialize database connection"""
    await Database.connect_db()


async def close_db():
    """Close database connection"""
    await Database.close_db()
