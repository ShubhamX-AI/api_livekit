"""Resolve the user-transcription source from the assistant's STT model + config."""

from src.core.config import settings
from src.core.logger import logger


def resolve_stt(assistant) -> tuple[str, dict]:
    """Return (provider, config) for user transcription. Unset means Sarvam, the default.

    "sarvam" runs Sarvam Saras v3 as a parallel audio tap (native-script Indic
    transcripts); "native" lets the conversational LLM transcribe itself
    (OpenAI gpt-4o-transcribe, or Gemini's own). Ignored in realtime (audio-out) mode.
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
