"""Resolve the user-transcription source from the assistant's STT model + config."""

from livekit.plugins import cartesia, deepgram, elevenlabs, sarvam

from src.core.config import settings
from src.core.logger import logger


def resolve_stt(assistant) -> tuple[str, dict]:
    """Return (provider, config) for user transcription. Unset means Sarvam, the default.

    "sarvam" runs Sarvam Saras v3 as a parallel audio tap (native-script Indic
    transcripts); "native" lets the conversational LLM transcribe itself
    (OpenAI gpt-4o-mini-transcribe, or Gemini's own); "cartesia", "deepgram" and
    "elevenlabs" are cascade-only plugins — resolved here but only instantiated by
    create_stt. Ignored in realtime (audio-out) mode.
    """
    model = assistant.assistant_stt_model or "sarvam"
    if model == "openai":
        # ponytail: pre-migration rows; delete once scripts/migrate_stt_config.py has run everywhere
        model = "native"
    config = assistant.assistant_stt_config or {}

    # Selecting a plugin STT disables the LLM's own transcription, so an unauthenticated
    # plugin means the call keeps no user transcripts at all. Degrade to native instead.
    key_var = {
        "sarvam": settings.SARVAM_API_KEY,
        "cartesia": settings.CARTESIA_API_KEY,
        "deepgram": settings.DEEPGRAM_API_KEY,
        "elevenlabs": settings.ELEVENLABS_API_KEY,
    }.get(model)
    plugin_model = model in {"sarvam", "cartesia", "deepgram", "elevenlabs"}
    if plugin_model and not (config.get("api_key") or key_var):
        logger.warning(
            f"No {model} API key for assistant {assistant.assistant_id} — falling back to native STT."
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

    if model == "deepgram":
        api_key = stt_config.get("api_key") or settings.DEEPGRAM_API_KEY
        if not api_key:
            logger.error(f"No Deepgram API key for cascade assistant {assistant_id}")
            return None
        interaction = getattr(assistant, "assistant_interaction_config", None)
        preferred = getattr(interaction, "preferred_languages", None)
        language = stt_config.get("language") or (preferred or ["en"])[0]
        deepgram_model = stt_config.get("model", "nova-3")
        kwargs: dict[str, object] = {}
        if stt_config.get("keyterm"):
            kwargs["keyterm"] = stt_config["keyterm"]
        # Two different Deepgram APIs behind one provider name. The nova family speaks
        # /listen/v1 (deepgram.STT); the flux family speaks the turn-based /listen/v2
        # (deepgram.STTv2) and ships its own endpointing. Neither class validates the
        # model at construction, so a flux ID sent to STT connects to v1 and fails there
        # — dispatch on the name instead.
        if deepgram_model.startswith("flux"):
            if stt_config.get("enable_diarization"):
                logger.warning(
                    f"enable_diarization is ignored on Deepgram '{deepgram_model}' "
                    f"(nova models only) for assistant {assistant_id}"
                )
            # language_hint, not language: v2 takes a hint and detects from there.
            return deepgram.STTv2(
                model=deepgram_model,
                language_hint=language,
                api_key=api_key,
                **kwargs,
            )
        # nova-3 is the multilingual default (45 languages; 'multi' auto-detects per segment).
        if stt_config.get("enable_diarization"):
            kwargs["enable_diarization"] = True
        return deepgram.STT(
            model=deepgram_model,
            language=language,
            api_key=api_key,
            **kwargs,
        )

    if model == "elevenlabs":
        api_key = stt_config.get("api_key") or settings.ELEVENLABS_API_KEY
        if not api_key:
            logger.error(f"No ElevenLabs API key for cascade assistant {assistant_id}")
            return None
        interaction = getattr(assistant, "assistant_interaction_config", None)
        preferred = getattr(interaction, "preferred_languages", None)
        language_code = stt_config.get("language_code") or (preferred or [None])[0]
        # Scribe v2 Real-Time auto-detects among ~190 languages when language_code is
        # omitted; no_verbatim cleans filler words out of the transcript.
        return elevenlabs.STT(
            model=stt_config.get("model", "scribe_v2_realtime"),
            language_code=language_code,
            no_verbatim=stt_config.get("no_verbatim", False),
            api_key=api_key,
        )

    logger.error(
        f"Unsupported cascade STT model {model!r} for assistant {assistant_id} "
        "— cascade supports 'sarvam', 'cartesia', 'deepgram' or 'elevenlabs'"
    )
    return None
