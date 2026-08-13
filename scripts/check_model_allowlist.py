"""Check every allowlisted OpenAI model against what the account can actually serve.

Read-only. Writes nothing, touches no database, and never prints the API key.

Why this exists: the model allowlists in `src/core/model_support/capabilities.py` and
`src/api/models/api_schemas/config/llm_config.py` are hand-maintained, and OpenAI retires
models on its own schedule — three `*-chat-latest` aliases were retired on 2026-06-19. An
allowlisted model that OpenAI no longer serves is the worst failure this platform has: the
Responses API answers 400 on *every* LLM turn, so the call connects, the caller hears
silence, and nothing in the request looked wrong at create time.

Run it before editing any allowlist, and after each `livekit-agents` bump:

    uv run python scripts/check_model_allowlist.py

Exit code is 1 when an allowlisted model is missing from the account's model list, so it
also works as a pre-deploy gate. `--json` prints the same result as one JSON object.

`GET /v1/models` returns what *this key's account* can reach, so a model missing here may be
missing for tiering reasons rather than retirement. Both cases are equally fatal at call
time for assistants on that key, which is why the report does not distinguish them.

## Being listed is not the same as working

The model list is necessary but not sufficient: OpenAI keeps deprecated ids in `/v1/models`
after they stop answering requests. So before adding a model back to an allowlist on the
strength of it appearing above, prove it answers:

    uv run python scripts/check_model_allowlist.py --probe gpt-5.2-chat-latest

That sends one 16-token Responses request (`store: false`) and prints what OpenAI says. It is
the only evidence that settles "listed but retired" either way — several ids can be listed and
still refuse every request.
"""

import asyncio
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from src.api.models.api_schemas.config.llm_config import (  # noqa: E402
    OPENAI_CASCADE_MODELS,
    OPENAI_REALTIME_MODELS,
)
from src.core.model_support.capabilities import (  # noqa: E402
    DEFAULT_CASCADE_MODEL,
    REALTIME_TRUNCATION_MODELS,
)
from src.core.config import settings  # noqa: E402

MODELS_URL = "https://api.openai.com/v1/models"
RESPONSES_URL = "https://api.openai.com/v1/responses"

# Ids in /v1/models that are irrelevant to this platform's LLM stages: audio, image,
# embedding and moderation endpoints all live in the same list.
_NON_LLM_MARKERS = (
    "transcribe",
    "whisper",
    "tts",
    "audio-preview",
    "embedding",
    "moderation",
    "dall-e",
    "image",
    "codex",
    "search",
    "computer-use",
    # gpt-audio / gpt-audio-mini are speech-to-speech models, not cascade LLMs.
    "audio",
)


async def fetch_available_models(api_key: str) -> set[str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        response = await client.get(
            MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}
        )
    if response.status_code != 200:
        # Body may echo request details but never the key itself; OpenAI redacts it.
        raise SystemExit(
            f"GET /v1/models failed with HTTP {response.status_code}: {response.text[:300]}"
        )
    return {item["id"] for item in response.json().get("data", [])}


def _is_candidate_chat_model(model_id: str) -> bool:
    """A plausible cascade LLM id — used only to keep the 'not allowlisted' list readable."""
    if any(marker in model_id for marker in _NON_LLM_MARKERS):
        return False
    if "realtime" in model_id:
        return False
    return model_id.startswith(("gpt-", "o1", "o3", "o4", "chat-latest"))


def build_report(available: set[str]) -> dict:
    lists = {
        "OPENAI_CASCADE_MODELS": set(OPENAI_CASCADE_MODELS),
        "OPENAI_REALTIME_MODELS": set(OPENAI_REALTIME_MODELS),
        "REALTIME_TRUNCATION_MODELS": set(REALTIME_TRUNCATION_MODELS),
    }
    missing = {name: sorted(models - available) for name, models in lists.items()}

    # Two drift checks that need no network call, only the lists themselves.
    internal = {
        # Every truncation-capable model must be one the API actually accepts, or the entry
        # is dead code that reads like coverage.
        "truncation_models_not_allowlisted": sorted(
            lists["REALTIME_TRUNCATION_MODELS"] - lists["OPENAI_REALTIME_MODELS"]
        ),
        # The cascade default has to be servable, or every assistant that omits `model`
        # fails.
        "default_cascade_model_allowlisted": DEFAULT_CASCADE_MODEL in OPENAI_CASCADE_MODELS,
        "default_cascade_model_available": DEFAULT_CASCADE_MODEL in available,
    }

    return {
        "available_count": len(available),
        "missing_from_openai": missing,
        "internal_drift": internal,
        "available_not_allowlisted": {
            "chat": sorted(
                m
                for m in available
                if _is_candidate_chat_model(m) and m not in lists["OPENAI_CASCADE_MODELS"]
            ),
            "realtime": sorted(
                m
                for m in available
                if "realtime" in m
                and "whisper" not in m
                and m not in lists["OPENAI_REALTIME_MODELS"]
            ),
        },
    }


def print_report(report: dict) -> None:
    print(f"Account can serve {report['available_count']} model id(s).\n")

    print("Allowlisted but NOT available (remove these — they cause silent calls):")
    any_missing = False
    for name, models in report["missing_from_openai"].items():
        if models:
            any_missing = True
            print(f"  {name}:")
            for model in models:
                print(f"      {model}")
    if not any_missing:
        print("  none — every allowlisted model is servable")

    drift = report["internal_drift"]
    print("\nInternal list drift (no network involved):")
    if drift["truncation_models_not_allowlisted"]:
        print(
            "  REALTIME_TRUNCATION_MODELS entries the API allowlist rejects (dead entries): "
            + ", ".join(drift["truncation_models_not_allowlisted"])
        )
    else:
        print("  REALTIME_TRUNCATION_MODELS is a subset of OPENAI_REALTIME_MODELS — ok")
    print(
        f"  DEFAULT_CASCADE_MODEL {DEFAULT_CASCADE_MODEL!r}: "
        f"allowlisted={drift['default_cascade_model_allowlisted']} "
        f"available={drift['default_cascade_model_available']}"
    )

    print("\nAvailable but not allowlisted (candidates to add, review before adding):")
    for kind, models in report["available_not_allowlisted"].items():
        print(f"  {kind}: {', '.join(models) if models else 'none'}")


async def probe_model(api_key: str, model: str) -> None:
    """Send one tiny request to `model` and print whether OpenAI actually answers.

    The decisive test for a model that appears in `/v1/models` but may be deprecated: the list
    is a catalogue, not a promise. Costs a handful of tokens.
    """
    payload = {"model": model, "input": "ping", "max_output_tokens": 16, "store": False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
        response = await client.post(
            RESPONSES_URL, headers={"Authorization": f"Bearer {api_key}"}, json=payload
        )
    if response.status_code < 400:
        print(f"{model}: WORKS (HTTP {response.status_code}) — safe to allowlist")
        raise SystemExit(0)

    try:
        error = (response.json().get("error") or {}).get("message") or response.text[:300]
    except ValueError:
        error = response.text[:300]
    print(f"{model}: REFUSED (HTTP {response.status_code})")
    print(f"  {error}")
    print("  Listed in /v1/models but not usable — do not allowlist it.")
    raise SystemExit(1)


async def main() -> None:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set — nothing to check against.")

    if "--probe" in sys.argv:
        index = sys.argv.index("--probe")
        if index + 1 >= len(sys.argv):
            raise SystemExit("--probe needs a model id, e.g. --probe gpt-5.2-chat-latest")
        await probe_model(api_key, sys.argv[index + 1])

    available = await fetch_available_models(api_key)
    report = build_report(available)

    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_report(report)

    broken = any(report["missing_from_openai"].values()) or not report["internal_drift"][
        "default_cascade_model_available"
    ]
    raise SystemExit(1 if broken else 0)


if __name__ == "__main__":
    asyncio.run(main())
