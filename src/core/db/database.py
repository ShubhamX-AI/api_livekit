from pymongo import AsyncMongoClient
from beanie import init_beanie
from src.core.config import settings
from src.core.db.db_schemas import (
    APIKey,
    Assistant,
    OutboundSIP,
    InboundSIP,
    InboundContextStrategy,
    CallRecord,
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
        """Initialize database connection and Beanie ODM"""
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
                    OutboundSIP,
                    InboundSIP,
                    InboundContextStrategy,
                    CallRecord,
                    Tool,
                    ActivityLog,
                    UsageRecord,
                ],
            )
            logger.info(f"Beanie initialized with database: {settings.DATABASE_NAME}")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def close_db(cls):
        """Close database connection"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB connection closed")


# Convenience functions for FastAPI lifespan events
async def init_db():
    """Initialize database connection"""
    await Database.connect_db()


async def close_db():
    """Close database connection"""
    await Database.close_db()
