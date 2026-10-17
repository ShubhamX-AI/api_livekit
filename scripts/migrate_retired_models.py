"""Move stored assistants off the OpenAI models this platform no longer accepts.

`gpt-5.1` and `gpt-5.4-nano` were taken off the allowlist on 2026-10-17 (OpenAI retires both
on 2027-04-01). An assistant still holding one keeps running until that date, but every
PATCH to it is refused, because the update is validated against the stored row. This moves
each one to the replacement LiveKit names:

    gpt-5.1       -> gpt-6-sol
    gpt-5.4-nano  -> gpt-6-luna

Both fields that can hold one are covered: `assistant_llm_config.model` (cascade) and
`assistant_llm_config.backend_model` (duplex). One knob changes with it: GPT-6 refuses
`reasoning_effort: "minimal"`, so a row holding it gets `"none"`, the nearest effort GPT-6
takes. Nothing else on the row is touched.

    uv run python scripts/migrate_retired_models.py            # dry run — prints, writes nothing
    uv run python scripts/migrate_retired_models.py --apply    # write

Idempotent: a second run finds nothing.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.config import settings  # noqa: E402

REPLACEMENTS = {"gpt-5.1": "gpt-6-sol", "gpt-5.4-nano": "gpt-6-luna"}
FIELDS = ("model", "backend_model")


def replacement_fields(llm_config: dict) -> dict[str, str]:
    """The `$set` this row needs, keyed by dotted path. Empty when it holds no retired model."""
    update = {
        f"assistant_llm_config.{field}": REPLACEMENTS[llm_config[field]]
        for field in FIELDS
        if llm_config.get(field) in REPLACEMENTS
    }
    if update and llm_config.get("reasoning_effort") == "minimal":
        update["assistant_llm_config.reasoning_effort"] = "none"
    return update


async def run(collection, apply: bool) -> int:
    query = {"$or": [{f"assistant_llm_config.{f}": {"$in": list(REPLACEMENTS)}} for f in FIELDS]}
    moved = 0
    async for doc in collection.find(query):
        update = replacement_fields(doc.get("assistant_llm_config") or {})
        if not update:
            continue
        moved += 1
        changes = ", ".join(f"{path.split('.')[-1]} -> {model}" for path, model in update.items())
        print(f"  {doc.get('assistant_id')}  mode={doc.get('assistant_mode')}  {changes}")
        if apply:
            await collection.update_one({"_id": doc["_id"]}, {"$set": update})

    verb = "Moved" if apply else "Would move"
    print(f"\n{verb} {moved} assistant(s).")
    if moved and not apply:
        print("Re-run with --apply to write.")
    return moved


async def main() -> None:
    apply = "--apply" in sys.argv
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    if not apply:
        print("Dry run — nothing will be written.\n")
    await run(client[settings.DATABASE_NAME]["assistants"], apply)


if __name__ == "__main__":
    asyncio.run(main())
