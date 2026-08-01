"""Fold an AgentSession's per-component usage into flat UsageRecord fields.

`session.usage` reports one typed entry per (provider, model) pair — an LLM entry, a
TTS entry, an STT entry, and one more of each if a model was swapped mid-call. The DB
record is flat, so the entries are summed per component here.

This replaces the deprecated UsageCollector/UsageSummary pair. Everything is in-process
aggregation of plugin metrics, so it works on a self-hosted server with no Cloud calls.
"""

from src.core.logger import logger


def _models(entries) -> str | None:
    """Comma-join the distinct model names seen, preserving order. None if empty."""
    names = list(dict.fromkeys(e.model for e in entries if e.model))
    return ", ".join(names) or None


def summarize_usage(session) -> dict:
    """Return UsageRecord field values for `session`. Never raises — usage is not
    worth losing a call record over, so on any failure it degrades to zeros."""
    try:
        entries = session.usage.model_usage
    except Exception as e:
        logger.warning(f"Could not read session usage: {e}")
        entries = []  # same code path below, so every field still gets its zero

    llm = [e for e in entries if e.type == "llm_usage"]
    tts = [e for e in entries if e.type == "tts_usage"]
    stt = [e for e in entries if e.type == "stt_usage"]

    def total(items, field: str):
        return sum(getattr(i, field, 0) or 0 for i in items)

    return {
        "llm_input_audio_tokens": total(llm, "input_audio_tokens"),
        "llm_input_text_tokens": total(llm, "input_text_tokens"),
        "llm_input_cached_audio_tokens": total(llm, "input_cached_audio_tokens"),
        "llm_input_cached_text_tokens": total(llm, "input_cached_text_tokens"),
        "llm_output_audio_tokens": total(llm, "output_audio_tokens"),
        "llm_output_text_tokens": total(llm, "output_text_tokens"),
        # Matches the previous definition (prompt + completion), which the admin
        # analytics endpoints already sum on.
        "llm_total_tokens": total(llm, "input_tokens") + total(llm, "output_tokens"),
        "llm_model": _models(llm),
        "tts_characters_count": total(tts, "characters_count"),
        "tts_audio_duration": total(tts, "audio_duration"),
        "stt_model": _models(stt),
        "stt_audio_duration": total(stt, "audio_duration"),
    }
