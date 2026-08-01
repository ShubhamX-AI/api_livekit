"""Factory for the conversational LLM used in cascade mode.

Only cascade mode needs this. The `pipeline` and `realtime` modes build a
`RealtimeModel` inline in session.py, because their LLM also owns STT (and, in
realtime, TTS) — there is nothing to factor out. Cascade is the only mode where
the LLM is a standalone stage.
"""

from livekit.plugins import openai

from src.core.config import settings
from src.core.logger import logger

# Kept as a plain string default, not a Literal. OpenAI ships models monthly and a
# Literal would mean a deploy per model; the supported set is documented instead
# (docs/architecture/cascade-pipeline.md).
DEFAULT_MODEL = "gpt-4.1"


def create_llm(assistant):
    """Build a non-realtime LLM from the assistant's LLM config. Returns None on error."""
    llm_config = assistant.assistant_llm_config or {}
    provider = (llm_config.get("provider") or "openai").lower()
    assistant_id = assistant.assistant_id

    if provider != "openai":
        logger.error(
            f"Unsupported cascade LLM provider {provider!r} for assistant {assistant_id} "
            "— cascade mode supports 'openai' only"
        )
        return None

    api_key = llm_config.get("api_key") or settings.OPENAI_API_KEY
    if not api_key:
        logger.error(f"No OpenAI API key for cascade assistant {assistant_id}")
        return None

    # responses.LLM is the recommended surface for the direct OpenAI API: cheaper than
    # chat-completions, and the same @function_tool contract, so DB-backed tools work
    # unchanged. openai.LLM stays the path for OpenAI-compatible third-party endpoints,
    # which this platform does not use.
    return openai.responses.LLM(
        model=llm_config.get("model") or DEFAULT_MODEL,
        api_key=api_key,
    )
