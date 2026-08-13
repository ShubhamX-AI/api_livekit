"""Ask OpenAI what it will accept, at config time, and cache the answer.

Two questions, both unanswerable offline:

- `unavailable_model_reason` — does this key's account still serve this model id?
- `rejected_config_reason` — will OpenAI accept this exact request (model + knobs + tool
  schemas)? One short probe request, so a knob value or a tool schema that the model refuses
  is a 422 at create/update instead of a call that connects and never speaks.


The static allowlists in `core/model_support/capabilities.py` are the first gate: they reject a
model this platform has never supported, instantly and offline. They cannot catch the second
case, which is the one that caused real outages — a model that *was* valid when the
allowlist was written and has since been retired. OpenAI retired three `*-chat-latest`
aliases on 2026-06-19; every assistant holding one kept passing validation and then answered
calls with silence, because the Responses API 400s on every turn for a model it no longer
serves.

So create/update also checks the model against `GET /v1/models` for the key the call will
actually use. Deliberately a *route-level* check, not a Pydantic validator: validators are
synchronous and run inside the event loop, and a network call there would block it.

Failure modes, in order of preference:

- model present  -> accept
- model absent   -> reject, naming the model (the caller can fix this)
- API unreachable / key rejected -> **accept**, with a warning log. A create/update must not
  become collateral damage of an OpenAI outage; the static allowlist has already had its say.

The cache is per key and per process. A retirement lands within `OPENAI_MODEL_CACHE_TTL`
(default 1h) without a deploy, which is the whole point of asking at all.
"""

import hashlib
import time

import httpx

from src.core.config import settings
from src.core.logger import logger
from src.core.model_support.payload import (
    build_responses_payload,
    gated_knob_signature,
)

MODELS_URL = "https://api.openai.com/v1/models"
RESPONSES_URL = "https://api.openai.com/v1/responses"

# {key_fingerprint: (expires_at_monotonic, frozenset_of_model_ids)}
_cache: dict[str, tuple[float, frozenset[str]]] = {}

# {(key_fingerprint, knob_signature): (expires_at_monotonic, error_message_or_None)}
_probe_cache: dict[tuple[str, str], tuple[float, str | None]] = {}


def _fingerprint(api_key: str) -> str:
    """Cache key that is not itself a credential — the cache dict ends up in memory dumps."""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def clear_cache() -> None:
    """Drop both caches. For tests and for an operator-triggered refresh."""
    _cache.clear()
    _probe_cache.clear()


async def available_models(api_key: str) -> frozenset[str] | None:
    """Model ids this key can serve, or None when OpenAI could not be asked.

    None is not an empty set: it means "unknown", and every caller treats unknown as
    permission to proceed. Returning an empty set instead would reject every model the
    moment OpenAI had a bad minute.
    """
    if not api_key:
        return None

    fingerprint = _fingerprint(api_key)
    cached = _cache.get(fingerprint)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(
                MODELS_URL, headers={"Authorization": f"Bearer {api_key}"}
            )
        if response.status_code != 200:
            # Includes 401 for a bad key. Not this check's job to reject the key: the call
            # itself will fail loudly on it, and guessing here would reject a key that is
            # merely rate-limited (429).
            logger.warning(
                "Could not list OpenAI models (HTTP %s) — skipping the live model check. "
                "The static allowlist still applies.",
                response.status_code,
            )
            return None
        models = frozenset(item["id"] for item in response.json().get("data", []))
    except Exception as e:
        logger.warning(
            "Could not list OpenAI models (%s: %s) — skipping the live model check. "
            "The static allowlist still applies.",
            type(e).__name__,
            e,
        )
        return None

    if not models:
        logger.warning("OpenAI returned an empty model list — skipping the live model check.")
        return None

    _cache[fingerprint] = (time.monotonic() + settings.OPENAI_MODEL_CACHE_TTL, models)
    logger.info("Cached %d OpenAI model id(s) for the live model check.", len(models))
    return models


async def unavailable_model_reason(model: str | None, api_key: str | None) -> str | None:
    """Why this key cannot run this model right now, or None when it can (or cannot be asked).

    The message is written for whoever sent the request, so it says what to do next rather
    than restating the model id the caller already typed.
    """
    if not model:
        return None

    models = await available_models(api_key or settings.OPENAI_API_KEY or "")
    if models is None or model in models:
        return None

    return (
        "the OpenAI account for this key does not serve it. Either the model has been "
        "retired by OpenAI or this account has no access to it. Pick a model the account "
        "serves — `uv run python scripts/check_model_allowlist.py` lists them. Storing it "
        "would produce a call that connects and then stays silent, because OpenAI rejects "
        "every turn."
    )


# The knobs a detail-free refusal could plausibly be about. Ordered by how often each one is
# the answer: `service_tier` availability is per-model *and* per-account, so it is the usual
# suspect on a model that is otherwise fine.
_SUSPECT_KNOBS = (
    "service_tier",
    "reasoning_effort",
    "verbosity",
    "temperature",
    "tool_choice",
    "parallel_tool_calls",
)


def _extract_error_message(body: dict, fallback: str) -> tuple[str, bool]:
    """Return `(message, actionable)` for OpenAI's refusal.

    `actionable` is whether OpenAI named the offending parameter. When it does, its own words
    beat anything we would write ("Unsupported value: 'reasoning.effort' does not support
    'none' with this model" — that names the knob and the value).

    It often does not. Over the Responses **WebSocket**, the transport the runtime uses, a
    rejection is an error frame with no detail at all ("There was an issue with your request.
    Please check your inputs and try again"), and — measured, not assumed — the same request
    over HTTPS can answer with exactly that text and no `param` either. So the caller has to
    handle both: quote OpenAI when it says something useful, and fall back to naming the
    candidates when it does not.
    """
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            param = error.get("param")
            if param:
                return f"{message} (param: {param})", True
            return str(message), False
    return fallback, False


def _candidate_knobs_hint(llm_config: dict | None) -> str:
    """What to try when OpenAI refuses the request without naming a parameter."""
    config = llm_config or {}
    present = [knob for knob in _SUSPECT_KNOBS if config.get(knob) is not None]
    if not present:
        return (
            " OpenAI named no parameter, and this config sets none of the optional knobs — so "
            "the request shape itself is the problem: most likely a function tool's schema. "
            "Reproduce it with `uv run python scripts/replay_cascade_request.py <assistant_id> "
            "--show-payload` and read the `tools` array."
        )
    return (
        " OpenAI named no parameter. The candidates, in the order they are usually the answer: "
        + ", ".join(present)
        + ". `service_tier` availability is per-model and per-account, so it leads that list. "
        "To find out which, clear them one at a time — or, for an assistant that is already "
        "stored, run `uv run python scripts/replay_cascade_request.py <assistant_id>`, which "
        "bisects the knobs automatically and names every offender."
    )


async def rejected_config_reason(
    model: str,
    api_key: str | None,
    llm_config: dict | None,
    *,
    tools: list[dict] | None = None,
    has_tools: bool = False,
) -> str | None:
    """Ask OpenAI to accept this exact request once. Return its refusal, or None.

    This is the gate that no static table can replace. Which `reasoning_effort` *values* a
    model takes, whether this account may use `service_tier: "flex"`, whether a tool schema is
    strict-valid — all of it is per-model and per-account, and OpenAI's own docs say only
    "some models support only a subset of these values". So the platform stops guessing and
    asks, once, at the moment the configuration is written.

    Cost is one short Responses call per distinct (key, model, knobs, tools-or-not)
    combination per `OPENAI_MODEL_CACHE_TTL`. Nothing is stored on OpenAI's side
    (`store: false`) and the reply is capped at 16 tokens.

    Failure is one-directional on purpose: a 4xx that names a parameter rejects the write, and
    anything else — network error, 401, 429, 5xx — accepts it. A create/update must not become
    collateral damage of an OpenAI outage, and the static rules have already had their say.
    """
    key = api_key or settings.OPENAI_API_KEY
    if not key or not model:
        return None

    signature = gated_knob_signature(model, llm_config, has_tools=has_tools)
    cache_key = (_fingerprint(key), signature)
    cached = _probe_cache.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    payload = build_responses_payload(
        model,
        llm_config,
        tools=tools,
        input_text="ping",
        max_output_tokens=16,
        store=False,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
            response = await client.post(
                RESPONSES_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
    except Exception as e:
        logger.warning(
            "Could not probe the OpenAI request shape (%s: %s) — skipping the live config "
            "check. The static rules still apply.",
            type(e).__name__,
            e,
        )
        return None

    reason: str | None = None
    if response.status_code == 400 or response.status_code == 422:
        try:
            body = response.json()
        except ValueError:
            body = {}
        reason, actionable = _extract_error_message(body, response.text[:300])
        if not actionable:
            # A refusal nobody can act on is only half a guard: the write is correctly
            # rejected, and the operator is left with "check your inputs".
            reason += _candidate_knobs_hint(llm_config)
        logger.info(
            "OpenAI rejected the probe for model=%s knobs=%s: %s",
            model,
            signature,
            reason,
        )
    elif response.status_code >= 400:
        # 401 (bad key), 429 (rate limited), 5xx (their problem). None of these say anything
        # about the configuration, so none of them may block the write.
        logger.warning(
            "OpenAI answered the config probe with HTTP %s — skipping the live config check.",
            response.status_code,
        )
        return None

    _probe_cache[cache_key] = (time.monotonic() + settings.OPENAI_MODEL_CACHE_TTL, reason)
    return reason
