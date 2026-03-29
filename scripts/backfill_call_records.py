"""
One-time backfill script to populate created_by_email on existing CallRecords.

Looks up Assistant.assistant_created_by_email via CallRecord.assistant_id
and sets created_by_email on each CallRecord that is missing it.

Usage:
    python -m scripts.backfill_call_records
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

load_dotenv(override=True)

from src.core.config import settings
from src.core.db.db_schemas import CallRecord, Assistant, UsageRecord, APIKey


async def backfill():
    client = AsyncIOMotorClient(settings.MONGODB_URL, tz_aware=True)
    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[CallRecord, Assistant, UsageRecord, APIKey],
    )

    # Build assistant_id -> created_by_email lookup
    assistants = await Assistant.find_all().to_list()
    lookup = {a.assistant_id: a.assistant_created_by_email for a in assistants}
    print(f"Loaded {len(lookup)} assistants for lookup")

    # Find all CallRecords missing created_by_email
    records = await CallRecord.find(
        CallRecord.created_by_email == None
    ).to_list()
    print(f"Found {len(records)} CallRecords missing created_by_email")

    updated = 0
    skipped = 0
    for record in records:
        email = lookup.get(record.assistant_id)
        if email:
            record.created_by_email = email
            await record.save()
            updated += 1
        else:
            skipped += 1

    print(f"Backfill complete: {updated} updated, {skipped} skipped (assistant not found)")
    client.close()


if __name__ == "__main__":
    asyncio.run(backfill())
