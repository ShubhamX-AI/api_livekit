"""Move STT settings out of assistant_interaction_config into their own model + config.

Legacy shape:
    assistant_interaction_config.user_stt_provider  ("sarvam" | "native" | "openai")
    assistant_interaction_config.stt_api_key

New shape (mirrors TTS):
    assistant_stt_model   ("sarvam" | "native")
    assistant_stt_config  ({"type": ..., "api_key": ...})

Run in two passes so no key is lost during the deploy window:

    uv run python scripts/migrate_stt_config.py            # copy — safe BEFORE deploying
    uv run python scripts/migrate_stt_config.py --unset     # cleanup — AFTER deploy is verified

Both passes are idempotent. Uses the raw collection, not the Beanie model: the legacy
fields no longer exist on Assistant, so an ODM round-trip would silently drop them.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.config import settings  # noqa: E402

LEGACY_PROVIDER = "assistant_interaction_config.user_stt_provider"
LEGACY_KEY = "assistant_interaction_config.stt_api_key"


def legacy_to_stt(interaction: dict) -> tuple[str, dict]:
    """Translate a legacy interaction config into (assistant_stt_model, assistant_stt_config)."""
    provider = interaction.get("user_stt_provider") or "sarvam"
    if provider == "openai":  # retired alias
        provider = "native"

    config = {"type": provider}
    api_key = interaction.get("stt_api_key")
    if provider == "sarvam" and api_key:
        config["api_key"] = api_key
    return provider, config


async def copy(collection) -> None:
    """Fill assistant_stt_model/config from the legacy pair. Skips assistants already migrated."""
    migrated = 0
    async for doc in collection.find({"assistant_stt_model": {"$in": [None, ""]}}):
        provider, config = legacy_to_stt(doc.get("assistant_interaction_config") or {})

        await collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"assistant_stt_model": provider, "assistant_stt_config": config}},
        )
        migrated += 1
        print(f"  {doc.get('assistant_id')} -> {provider}{' (+api_key)' if 'api_key' in config else ''}")

    print(f"Copied STT settings for {migrated} assistant(s).")


async def unset(collection) -> None:
    """Drop the legacy fields. Only touches assistants that already have the new model set."""
    result = await collection.update_many(
        {
            "assistant_stt_model": {"$nin": [None, ""]},
            "$or": [{LEGACY_PROVIDER: {"$exists": True}}, {LEGACY_KEY: {"$exists": True}}],
        },
        {"$unset": {LEGACY_PROVIDER: "", LEGACY_KEY: ""}},
    )
    print(f"Removed legacy STT fields from {result.modified_count} assistant(s).")

    stragglers = await collection.count_documents(
        {
            "assistant_stt_model": {"$in": [None, ""]},
            "$or": [{LEGACY_PROVIDER: {"$exists": True}}, {LEGACY_KEY: {"$exists": True}}],
        }
    )
    if stragglers:
        print(f"WARNING: {stragglers} assistant(s) still carry legacy fields but no assistant_stt_model. Run the copy pass first.")


async def main() -> None:
    do_unset = "--unset" in sys.argv

    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    collection = client[settings.DATABASE_NAME]["assistants"]

    if do_unset:
        await unset(collection)
    else:
        await copy(collection)
        print("Deploy the new code, verify, then re-run with --unset.")


if __name__ == "__main__":
    asyncio.run(main())
