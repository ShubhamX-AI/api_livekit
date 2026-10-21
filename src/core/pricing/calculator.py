"""Pure pricing calculation over normalized model usage entries."""

from dataclasses import dataclass
from decimal import Decimal

from src.core.pricing.rates import (
    PRICING_SCHEMA_VERSION,
    SERVICE_TIER_MULTIPLIER,
    ModelRate,
    get_rate,
)


@dataclass(frozen=True)
class PricingResult:
    estimated_cost_usd: Decimal
    pricing_schema_version: int
    pricing_complete: bool
    model_usage: list[dict]
    unpriced_model_usage: list[dict]


def _number(entry: dict, key: str) -> Decimal:
    return Decimal(str(entry.get(key, 0) or 0))


def _cost(entry: dict, rate: ModelRate) -> Decimal:
    cached_total = _number(entry, "input_cached_tokens")
    cached_text = _number(entry, "input_cached_text_tokens")
    cached_audio = _number(entry, "input_cached_audio_tokens")
    cached_image = _number(entry, "input_cached_image_tokens")
    if cached_total and not cached_text and not cached_audio and not cached_image:
        if rate.input_audio or rate.cached_input_audio:
            cached_audio = cached_total
        else:
            cached_text = cached_total
    input_text = max(_number(entry, "input_text_tokens"), cached_text)
    input_audio = max(_number(entry, "input_audio_tokens"), cached_audio)
    input_image = max(_number(entry, "input_image_tokens"), cached_image)
    input_total = _number(entry, "input_tokens")
    if not input_text and not input_audio and not input_image and input_total:
        if rate.input_audio or rate.cached_input_audio:
            input_audio = input_total
        else:
            input_text = input_total
    output_text = _number(entry, "output_text_tokens")
    output_audio = _number(entry, "output_audio_tokens")
    output_total = _number(entry, "output_tokens")
    if not output_text and not output_audio and output_total:
        if rate.output_audio:
            output_audio = output_total
        else:
            output_text = output_total
    return (
        (input_text - cached_text) * rate.input_text
        + cached_text * rate.cached_input_text
        + (input_audio - cached_audio) * rate.input_audio
        + cached_audio * rate.cached_input_audio
        + (input_image - cached_image) * rate.input_image
        + rate.cache_creation * _number(entry, "input_cache_creation_tokens")
        + rate.output_text * output_text
        + rate.output_audio * output_audio
        + rate.audio_second * _number(entry, "audio_duration")
        + rate.session_second * _number(entry, "session_duration")
        + rate.character * _number(entry, "characters_count")
    )


def _tier_multiplier(rate: ModelRate, service_tier: str | None) -> Decimal | None:
    """Factor the OpenAI `service_tier` applies to this rate, or None when it is not known.

    The tier is a backend setting. GPT-Live's voice model is billed per second of session, so a
    tier never touches it — in duplex mode it must keep its price while the backend model's
    token rate scales. Realtime-API models have no published tier price, so they stay unpriced
    rather than guessed.
    """
    if service_tier in (None, "auto", "default") or rate.session_second:
        return Decimal(1)
    if rate.input_audio or rate.output_audio:
        return None
    return SERVICE_TIER_MULTIPLIER.get(service_tier)


def price_model_usage(model_usage: list[dict], pricing_context: dict | None = None) -> PricingResult:
    """Price each billable entry, retaining unknown entries as an explicit partial result."""
    pricing_context = pricing_context or {}
    service_tier = pricing_context.get("openai_service_tier")
    total = Decimal(0)
    unpriced = []
    enriched = []
    for original in model_usage:
        entry = dict(original)
        rate = get_rate(entry.get("type", ""), entry.get("provider", ""), entry.get("model", ""))
        multiplier = Decimal(1)
        if rate is not None and entry.get("provider") == "openai" and entry.get("type") == "llm_usage":
            multiplier = _tier_multiplier(rate, service_tier)
        if rate is None or multiplier is None:
            entry["pricing_complete"] = False
            unpriced.append(entry)
            enriched.append(entry)
            continue
        cost = _cost(entry, rate) * multiplier
        entry["estimated_cost_usd"] = cost
        entry["pricing_complete"] = True
        enriched.append(entry)
        total += cost
    return PricingResult(
        estimated_cost_usd=total,
        pricing_schema_version=PRICING_SCHEMA_VERSION,
        pricing_complete=not unpriced,
        model_usage=enriched,
        unpriced_model_usage=unpriced,
    )


def duplex_cost_split(model_usage: list[dict]) -> dict:
    """Split a duplex call's priced entries into the voice model and the backend model.

    GPT-Live reports two entries: the voice model by `session_duration` and the backend
    Responses model by tokens. `estimated_cost_usd` is their sum, which hides what the
    backend cost. Works on stored entries too, whose costs were serialized as strings.
    An entry that could not be priced adds nothing, so a split that falls short of the total
    is explained by `unpriced_model_usage`.
    """
    parts = {"voice": [], "backend": []}
    for entry in model_usage:
        if entry.get("type") != "llm_usage":
            continue
        role = "voice" if entry.get("session_duration") else "backend"
        parts[role].append(entry)

    def cost(entries: list[dict]) -> Decimal:
        return sum((Decimal(str(e.get("estimated_cost_usd") or 0)) for e in entries), Decimal(0))

    def models(entries: list[dict]) -> str | None:
        return ", ".join(dict.fromkeys(e["model"] for e in entries if e.get("model"))) or None

    return {
        "voice_model": models(parts["voice"]),
        "backend_model": models(parts["backend"]),
        "estimated_cost_voice_usd": cost(parts["voice"]),
        "estimated_cost_backend_usd": cost(parts["backend"]),
    }
