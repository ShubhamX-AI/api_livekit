"""
One-time backfill script to populate billable_duration_minutes on existing CallRecords.

Usage:
    python -m scripts.backfill_billable_duration_minutes
"""

import asyncio

from beanie import init_beanie
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(override=True)

from src.core.billing import calculate_billable_duration_minutes
from src.core.config import settings
from src.core.db.db_schemas import APIKey, Assistant, CallRecord, UsageRecord


async def backfill():
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        tz_aware=True,
        serverSelectionTimeoutMS=5000,
    )
    await client.admin.command("ping")
    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[CallRecord, Assistant, UsageRecord, APIKey],
    )

    records = await CallRecord.find(
        CallRecord.billable_duration_minutes == None
    ).to_list()
    print(f"Found {len(records)} CallRecords missing billable_duration_minutes")

    updated = 0
    skipped = 0
    for record in records:
        billable_duration_minutes = calculate_billable_duration_minutes(
            call_status=record.call_status,
            call_duration_minutes=record.call_duration_minutes,
        )
        if billable_duration_minutes is None:
            skipped += 1
            continue

        record.billable_duration_minutes = billable_duration_minutes
        await record.save()
        updated += 1

    print(
        "Backfill complete: "
        f"{updated} updated, {skipped} skipped (duration missing and status not billable)"
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(backfill())
