from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.core.providers.keys import ProviderApiKey


# ── STT Config sub-models ──────────────────────────
class NativeSTTConfig(BaseModel):
    """No knobs — the conversational LLM transcribes itself with the prompt built at runtime."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["native"] = "native"  # discriminator field


class SarvamSTTConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["sarvam"] = "sarvam"
    model: str = Field("saaras:v3", max_length=40, description="Sarvam STT model: saaras:v3 (recommended), saaras:v2.5 or saarika:v2.5")
    language: str = Field("unknown", max_length=10, description="BCP-47 language code, or 'unknown' to auto-detect")
    mode: str = Field("codemix", max_length=20, description="Transcription mode (saaras:v3 only): codemix (default — keeps code-switching intact), transcribe, translate, verbatim or translit")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="Sarvam API key for the parallel STT tap (optional, falls back to system SARVAM_API_KEY). Distinct from assistant_tts_config.api_key, which belongs to the selected TTS provider.")


class CartesiaSTTConfig(BaseModel):
    """Cascade mode only. Cartesia STT cannot auto-detect, so language is always fixed."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["cartesia"] = "cartesia"
    model: str = Field("ink-whisper", max_length=40, description="ink-whisper (43 languages, one at a time) or ink-2 (English only)")
    language: Optional[str] = Field(None, max_length=10, description="Fixed language code — Cartesia STT has no auto-detect. When omitted, falls back to the first entry of assistant_interaction_config.preferred_languages, then 'en'. Use Sarvam for multilingual calls.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="Cartesia API key (optional, falls back to system CARTESIA_API_KEY). Distinct from assistant_tts_config.api_key.")


class DeepgramSTTConfig(BaseModel):
    """Cascade mode only. nova-3 is multilingual (45 languages); 'multi' auto-detects per segment."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["deepgram"] = "deepgram"
    model: str = Field("nova-3", max_length=40, description="Deepgram STT model: nova-3 (default — multilingual, 45 languages), nova-2, flux-general-en (English only) or flux-general-multi (multilingual).")
    language: Optional[str] = Field(None, max_length=10, description="Language — any BCP-47 code, or 'multi' for multilingual auto-detection. When omitted, falls back to the first entry of assistant_interaction_config.preferred_languages, then the provider default.")
    enable_diarization: bool = Field(False, description="Enable speaker diarization (nova models).")
    keyterm: Optional[Union[str, List[str]]] = Field(None, max_length=200, description="One or more terms to boost recognition (nova-3 / flux). Nova-2 uses keywords instead.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="Deepgram API key (optional, falls back to system DEEPGRAM_API_KEY).")


class ElevenLabsSTTConfig(BaseModel):
    """Cascade mode only. Scribe v2 Real-Time auto-detects among 100+ languages when language_code is omitted."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["elevenlabs"] = "elevenlabs"
    model: str = Field("scribe_v2_realtime", max_length=40, description="ElevenLabs STT model: scribe_v2_realtime (default), scribe_v2 or scribe_v1.")
    language_code: Optional[str] = Field(None, max_length=10, description="BCP-47 language code. When omitted, Scribe v2 Real-Time auto-detects among ~190 languages; otherwise it falls back to the first entry of assistant_interaction_config.preferred_languages.")
    no_verbatim: bool = Field(False, description="Strips filler words, false starts and disfluencies from the transcript for cleaner output.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="ElevenLabs API key for the STT stage (optional, falls back to system ELEVENLABS_API_KEY, the same variable the TTS stage uses). Distinct from assistant_tts_config.api_key, which belongs to whichever provider the TTS stage selected.")


STTConfig = Annotated[
    Union[
        NativeSTTConfig,
        SarvamSTTConfig,
        CartesiaSTTConfig,
        DeepgramSTTConfig,
        ElevenLabsSTTConfig,
    ],
    Field(discriminator="type"),
]
