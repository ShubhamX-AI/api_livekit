"""Clean stored TTS configs the API now refuses (1.6.0).

Three things that used to be accepted and did nothing, or failed every call:

- an ElevenLabs model ElevenLabs has retired (`eleven_monolingual_v1`, `eleven_multilingual_v1`,
  400 `unsupported_model` on every synthesis) — moved to `eleven_multilingual_v2`, which
  ElevenLabs names as a replacement and which reads every voice setting;
- an ElevenLabs voice setting the stored model does not read (`speed` on `eleven_v3`, …) —
  removed;
- `temperature` on Sarvam `bulbul:v4-flash`, which Sarvam fixes at 0.6 — removed.

The worker already drops the ignored settings at call time, so none of this changes what a
caller hears except the v1 move, which turns a silent call into a working one. What it fixes
is editing: resending such a config is now a 422.

    uv run python scripts/migrate_tts_settings.py            # dry run — prints, writes nothing
    uv run python scripts/migrate_tts_settings.py --apply    # write

Idempotent: a second run finds nothing.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.core.model_support.speech import (  # noqa: E402
    ELEVENLABS_RETIRED_TTS_MODELS,
    unread_elevenlabs_settings,
)

ELEVENLABS_REPLACEMENT = "eleven_multilingual_v2"
PREFIX = "assistant_tts_config"


def tts_fixes(tts_model: str | None, tts_config: dict) -> tuple[dict, list[str]]:
    """The `$set` and the `$unset` paths this row needs. Both empty when it is clean."""
    if tts_model == "elevenlabs":
        model = tts_config.get("model") or "eleven_v3"
        if model in ELEVENLABS_RETIRED_TTS_MODELS:
            return {f"{PREFIX}.model": ELEVENLABS_REPLACEMENT}, []
        unread = unread_elevenlabs_settings(model, tts_config.get("voice_settings"))
        return {}, [f"{PREFIX}.voice_settings.{key}" for key in unread]
    v4_flash = tts_model == "sarvam" and tts_config.get("model") == "bulbul:v4-flash"
    if v4_flash and tts_config.get("temperature") is not None:
        return {}, [f"{PREFIX}.temperature"]
    return {}, []


async def run(collection, apply: bool) -> int:
    fixed = 0
    async for doc in collection.find({"assistant_tts_model": {"$in": ["elevenlabs", "sarvam"]}}):
        to_set, to_unset = tts_fixes(doc.get("assistant_tts_model"), doc.get(PREFIX) or {})
        if not to_set and not to_unset:
            continue
        fixed += 1
        changes = [f"{path.split('.')[-1]} -> {value}" for path, value in to_set.items()]
        changes += [f"remove {path.split('.')[-1]}" for path in to_unset]
        print(f"  {doc.get('assistant_id')}  tts={doc.get('assistant_tts_model')}  {', '.join(changes)}")
        if apply:
            update = {}
            if to_set:
                update["$set"] = to_set
            if to_unset:
                update["$unset"] = {path: "" for path in to_unset}
            await collection.update_one({"_id": doc["_id"]}, update)

    verb = "Fixed" if apply else "Would fix"
    print(f"\n{verb} {fixed} assistant(s).")
    if fixed and not apply:
        print("Re-run with --apply to write.")
    return fixed


async def main() -> None:
    apply = "--apply" in sys.argv
    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    if not apply:
        print("Dry run — nothing will be written.\n")
    await run(client[settings.DATABASE_NAME]["assistants"], apply)


if __name__ == "__main__":
    asyncio.run(main())
