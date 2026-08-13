"""Drop cascade LLM knobs the assistant's stored model cannot read.

`temperature`, `reasoning_effort` and `verbosity` are model-gated (see
src/core/model_support/capabilities.py). Rows written before that gate existed can hold a
knob the model rejects — e.g. `temperature` on `gpt-5-mini`. OpenAI answers such a request
with a 400 on *every* LLM turn, so the call connects and the assistant never speaks.

`create_llm` already drops a stale knob at call time, so a row like this is not a live
outage once the agent image is current. What it still blocks is editing the assistant:
`enforce_stored_mode_constraints` judges a PATCH against the merged row, so any update to
that assistant is refused with a 400 until the knob is cleared. This clears them in bulk.

    uv run python scripts/migrate_llm_knobs.py            # dry run — prints, writes nothing
    uv run python scripts/migrate_llm_knobs.py --apply    # write

Idempotent. Only cascade assistants are considered: the knobs are inert in the other two
modes, and the "no model set" default (gpt-4.1) is a cascade default. Uses the raw
collection to leave every other field on the document exactly as it is.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from src.core.model_support.capabilities import (  # noqa: E402
    DEFAULT_CASCADE_MODEL,
    unsupported_knob_reason,
)
from src.core.config import settings  # noqa: E402

GATED_KNOBS = ("temperature", "reasoning_effort", "verbosity")


def stale_knobs(llm_config: dict) -> dict[str, str]:
    """Which knobs on this config the stored model rejects, and why. Empty when it is clean.

    `has_tools` is left at its default False: whether a session attaches function tools is
    not a property of the row, and the reasoning/tools pairing is handled at call time by
    create_llm. Clearing a knob here on that basis would remove one the operator can
    legitimately use on a toolless assistant.
    """
    model = llm_config.get("model") or DEFAULT_CASCADE_MODEL
    reasons = {}
    for knob in GATED_KNOBS:
        if llm_config.get(knob) is None:
            continue
        reason = unsupported_knob_reason(model, knob)
        if reason:
            reasons[knob] = reason
    return reasons


async def run(collection, apply: bool) -> None:
    scanned = affected = 0

    async for doc in collection.find({"assistant_mode": "cascade"}):
        scanned += 1
        llm_config = doc.get("assistant_llm_config") or {}
        reasons = stale_knobs(llm_config)
        if not reasons:
            continue

        affected += 1
        model = llm_config.get("model") or f"{DEFAULT_CASCADE_MODEL} (unset)"
        print(f"  {doc.get('assistant_id')} | model={model}")
        for knob, reason in reasons.items():
            print(f"      drop {knob}={llm_config[knob]!r} — {reason}")

        if apply:
            await collection.update_one(
                {"_id": doc["_id"]},
                {"$unset": {f"assistant_llm_config.{knob}": "" for knob in reasons}},
            )

    verb = "Cleared" if apply else "Would clear"
    print(f"{verb} stale knobs on {affected} of {scanned} cascade assistant(s).")
    if affected and not apply:
        print("Re-run with --apply to write.")


async def main() -> None:
    apply = "--apply" in sys.argv

    print(f"Connecting to MongoDB at {settings.MONGODB_URL}...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    collection = client[settings.DATABASE_NAME]["assistants"]

    if not apply:
        print("Dry run — nothing will be written.")
    await run(collection, apply)


if __name__ == "__main__":
    asyncio.run(main())
