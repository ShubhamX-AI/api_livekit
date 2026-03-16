import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from src.core.db.db_schemas import Assistant, APIKey, OutboundSIP, CallRecord, Tool, ActivityLog
from src.core.config import settings

async def migrate():
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    
    # Initialize Beanie with all models used in the app
    await init_beanie(
        database=client[settings.DATABASE_NAME], 
        document_models=[Assistant, APIKey, OutboundSIP, CallRecord, Tool, ActivityLog]
    )

    print("Fetching all assistants...")
    assistants = await Assistant.find_all().to_list()
    
    migrated_count = 0
    for assistant in assistants:
        # Beanie's model_validator(mode="before") automatically handles the 
        # translation of legacy flat fields into the nested interaction config 
        # upon loading. We just need to save it back to update the DB structure.
        await assistant.save()
        migrated_count += 1
        print(f"Migrated assistant: {assistant.assistant_name} ({assistant.assistant_id})")

    print(f"\nSuccessfully migrated {migrated_count} assistants to the new nested configuration structure.")

if __name__ == "__main__":
    asyncio.run(migrate())
