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
    language: Optional[str] = Field(None, max_length=10, description="Fixed language code, ISO 639-1 ('en', 'hi') — NOT BCP-47; 'en-US' is rejected and ignored. Cartesia STT has no auto-detect, so omitting this means English. Use Sarvam or Deepgram nova-3 for multilingual calls.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="Cartesia API key (optional, falls back to system CARTESIA_API_KEY). Distinct from assistant_tts_config.api_key.")


class DeepgramSTTConfig(BaseModel):
    """Cascade mode only. nova-3 is multilingual (45 languages); 'multi' auto-detects per segment."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["deepgram"] = "deepgram"
    model: str = Field("nova-3", max_length=40, description="Deepgram STT model: nova-3 (default — multilingual, 45 languages), nova-2, flux-general-en (English only) or flux-general-multi (multilingual).")
    language: Optional[str] = Field(None, max_length=10, description="Language — any BCP-47 code ('en-US', 'hi-IN'), or 'multi' to auto-detect per segment. A 3-letter code such as 'hin' is rejected and ignored. Omitting this auto-detects on nova-3 and flux-general-multi ('multi', billed at a higher per-minute rate); nova-2 and flux-general-en cannot detect and stay on 'en-US'. On the flux models this becomes a language_hint, which flux-general-multi alone accepts.")
    enable_diarization: bool = Field(False, description="Enable speaker diarization (nova models).")
    keyterm: Optional[Union[str, List[str]]] = Field(None, max_length=200, description="One or more terms to boost recognition (nova-3 / flux). Nova-2 uses keywords instead.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="Deepgram API key (optional, falls back to system DEEPGRAM_API_KEY).")


class ElevenLabsSTTConfig(BaseModel):
    """Cascade mode only. Scribe v2 Real-Time auto-detects unless language_code pins a language."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["elevenlabs"] = "elevenlabs"
    model: str = Field("scribe_v2_realtime", max_length=40, description="ElevenLabs STT model: scribe_v2_realtime (default), scribe_v2 or scribe_v1.")
    language_code: Optional[str] = Field(None, max_length=10, description="ISO 639-3 language code ('eng', 'hin', 'ben') — NOT BCP-47 and NOT ISO 639-1. Scribe closes the connection with '1008 invalid_request' on anything else, so an unrecognized code is rejected and ignored here instead. Omit to auto-detect among ~190 languages, which is what this provider is for; setting it disables auto-detect.")
    no_verbatim: bool = Field(False, description="Strips filler words, false starts and disfluencies from the transcript for cleaner output.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="ElevenLabs API key for the STT stage (optional, falls back to system ELEVENLABS_API_KEY, the same variable the TTS stage uses). Distinct from assistant_tts_config.api_key, which belongs to whichever provider the TTS stage selected.")


class OpenAISTTConfig(BaseModel):
    """Cascade mode only. Streams over OpenAI's realtime transcription WebSocket by default."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["openai"] = "openai"
    model: str = Field("gpt-4o-mini-transcribe", max_length=40, description="OpenAI STT model: gpt-4o-mini-transcribe (default — fast and cheap), gpt-4o-transcribe (more accurate) or whisper-1. 'gpt-realtime-whisper' is rejected: it has no server-side endpointing and needs a client-side VAD this runtime cannot supply.")
    language: Optional[str] = Field(None, max_length=10, description="ISO 639-1 language code ('en', 'hi') — NOT BCP-47; 'hi-IN' is rejected and ignored. Omitting this turns detect_language on rather than pinning English. Ignored when detect_language is true.")
    detect_language: bool = Field(False, description="Auto-detect the spoken language instead of pinning one. Overrides `language`.")
    prompt: Optional[str] = Field(None, max_length=500, description="Text prompt biasing the transcription (names, jargon, spellings). whisper-1 only — the gpt-4o transcribe models ignore it.")
    noise_reduction_type: Optional[Literal["near_field", "far_field"]] = Field(None, description="Server-side noise reduction: 'near_field' for headsets, 'far_field' for speakerphone/room mics. Omit for none.")
    use_realtime: bool = Field(True, description="Stream over the realtime transcription WebSocket (interim results, low latency). Set false to use the batch REST transcription API — cheaper, but adds a full utterance of latency per turn.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=100, description="OpenAI API key for the STT stage (optional, falls back to system OPENAI_API_KEY — the same variable the cascade LLM uses). Distinct from assistant_tts_config.api_key.")


STTConfig = Annotated[
    Union[
        NativeSTTConfig,
        SarvamSTTConfig,
        CartesiaSTTConfig,
        DeepgramSTTConfig,
        ElevenLabsSTTConfig,
        OpenAISTTConfig,
    ],
    Field(discriminator="type"),
]
