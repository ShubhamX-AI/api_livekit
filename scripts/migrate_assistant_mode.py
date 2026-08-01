"""Rename the runtime-mode field: it never selected an LLM, it selects the whole
session shape (pipeline / realtime / cascade). The old name mixed those up.

    assistants.assistant_llm_mode  -> assistants.assistant_mode
    usage_records.llm_mode         -> usage_records.mode

This is a hard break, not a compat shim (the API also stops accepting the old
request key, see reject_retired_mode_key in src/api/models/api_schemas.py) — so a
single idempotent $rename per collection is enough, no copy/unset window needed.

Run AFTER deploying the renamed code, then run it again once: old code instances
still writing during the deploy window create fresh docs with the old key, so one
extra pass catches stragglers. A second run reporting 0 modified means it's done.
Any doc still missing assistant_mode falls back to the Beanie default "pipeline"
(same as before this rename), so the only risk window is a cascade/realtime
assistant briefly behaving as pipeline if a call lands between deploy and the
first script run.

    uv run python scripts/migrate_assistant_mode.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.config import settings  # noqa: E402


async def rename_field(collection, old_key: str, new_key: str, label: str) -> None:
    result = await collection.update_many(
        {old_key: {"$exists": True}},
        {"$rename": {old_key: new_key}},
    )
    print(
        f"{label}: renamed {old_key} -> {new_key} on "
        f"{result.modified_count} of {result.matched_count} document(s)."
    )


async def main() -> None:
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    await rename_field(db["assistants"], "assistant_llm_mode", "assistant_mode", "assistants")
    await rename_field(db["usage_records"], "llm_mode", "mode", "usage_records")


if __name__ == "__main__":
    asyncio.run(main())
