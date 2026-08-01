"""Resolve the user-transcription source from the assistant's STT model + config."""

from livekit.plugins import cartesia, sarvam

from src.core.config import settings
from src.core.logger import logger


def resolve_stt(assistant) -> tuple[str, dict]:
    """Return (provider, config) for user transcription. Unset means Sarvam, the default.

    "sarvam" runs Sarvam Saras v3 as a parallel audio tap (native-script Indic
    transcripts); "native" lets the conversational LLM transcribe itself
    (OpenAI gpt-4o-mini-transcribe, or Gemini's own). Ignored in realtime (audio-out) mode.
    """
    model = assistant.assistant_stt_model or "sarvam"
    if model == "openai":
        # ponytail: pre-migration rows; delete once scripts/migrate_stt_config.py has run everywhere
        model = "native"
    config = assistant.assistant_stt_config or {}

    # Selecting Sarvam disables the LLM's own transcription, so an unauthenticated tap
    # means the call keeps no user transcripts at all. Degrade to native instead.
    if model == "sarvam" and not (config.get("api_key") or settings.SARVAM_API_KEY):
        logger.warning(
            f"No Sarvam API key for assistant {assistant.assistant_id} — falling back to native STT"
        )
        return "native", {}

    return model, config


def create_stt(assistant):
    """Build a plugin STT instance for cascade mode. Returns None on error.

    Distinct from resolve_stt: cascade puts STT on the AgentSession as a first-class
    stage, so "native" (the conversational LLM transcribing itself) has no meaning
    here — there is no realtime model in the loop to do it.
    """
    stt_config = assistant.assistant_stt_config or {}
    model = assistant.assistant_stt_model or "sarvam"
    assistant_id = assistant.assistant_id

    if model == "sarvam":
        api_key = stt_config.get("api_key") or settings.SARVAM_API_KEY
        if not api_key:
            logger.error(f"No Sarvam API key for cascade assistant {assistant_id}")
            return None
        # The multilingual default: language "unknown" auto-detects, and mode "codemix"
        # (saaras:v3 only) keeps code-switching intact inside a single utterance.
        # interaction_config.preferred_languages needs no wiring here — auto-detect
        # already covers every language it could list, and pinning one would be strictly
        # worse for a caller who switches mid-call. Set `language` explicitly to pin.
        return sarvam.STT(
            model=stt_config.get("model", "saaras:v3"),
            mode=stt_config.get("mode", "codemix"),
            language=stt_config.get("language", "unknown"),
            api_key=api_key,
            sample_rate=16000,
        )

    if model == "cartesia":
        api_key = stt_config.get("api_key") or settings.CARTESIA_API_KEY
        if not api_key:
            logger.error(f"No Cartesia API key for cascade assistant {assistant_id}")
            return None
        # Cartesia STT cannot auto-detect, so exactly one language gets transcribed. When
        # the config does not pin one, honour the first preferred language rather than
        # silently defaulting a Hindi assistant to English.
        interaction = getattr(assistant, "assistant_interaction_config", None)
        preferred = getattr(interaction, "preferred_languages", None)
        language = stt_config.get("language") or (preferred or ["en"])[0]
        # ponytail: model pinned, never left to the plugin default. That default flipped
        # to the English-only ink-2 in livekit-agents 1.5.15; ink-whisper is the
        # 43-language one.
        return cartesia.STT(
            model=stt_config.get("model", "ink-whisper"),
            language=language,
            api_key=api_key,
        )

    logger.error(
        f"Unsupported cascade STT model {model!r} for assistant {assistant_id} "
        "— cascade supports 'sarvam' or 'cartesia'"
    )
    return None
