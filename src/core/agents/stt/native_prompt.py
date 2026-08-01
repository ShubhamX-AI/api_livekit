"""Transcription prompt for the `native` STT path — the conversational LLM transcribing itself.

Only OpenAI accepts a transcription prompt (`AudioTranscription.prompt`). Gemini's
`AudioTranscriptionConfig` takes no arguments, so on a Gemini assistant none of this applies
and the model transcribes on its own defaults.
"""

from __future__ import annotations

from typing import Sequence

# OpenAI's far-field noise-reduction model is trained on lossy PSTN / G.711 audio.
# near_field assumes a close mic or headset and measurably degrades phone transcription.
NEAR_FIELD = "near_field"
FAR_FIELD = "far_field"


def noise_reduction_for(is_phone_call: bool) -> str:
    return FAR_FIELD if is_phone_call else NEAR_FIELD


def build_native_stt_prompt(
    preferred_languages: Sequence[str] | None,
    *,
    is_phone_call: bool,
) -> str:
    """Steer the transcription model toward literal, native-script output.

    `preferred_languages` is a hint only — the language is never pinned as an API parameter,
    so a caller who switches language mid-call is still transcribed correctly.
    """
    langs = list(preferred_languages or [])
    language_hint = f"Expected language(s): {', '.join(langs)}. " if langs else ""
    phone_note = (
        "Audio is from a live telephone call (G.711 narrowband, ~8 kHz, lossy). "
        "Expect static, line hum, codec artifacts, and muffled consonants. "
        "Do NOT treat noise as speech. "
        if is_phone_call
        else ""
    )
    return (
        f"{language_hint}"
        f"{phone_note}"
        "This is a live customer support voice call. The speaker may use any language or mix languages mid-sentence. "
        "Transcribe ONLY what is actually spoken, in the speaker's natural script for that language. "
        "If audio is unclear, silent, or unintelligible — output [inaudible]. NEVER guess or fabricate words. "
        "For mixed speech, transcribe each word in its own correct native script. "
        "Do NOT romanize. Do NOT translate. Do NOT switch to a different language than what was spoken. "
        "Use natural punctuation. Skip filler sounds like um, uh, hmm."
    )
