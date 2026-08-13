from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from src.core.providers.keys import ProviderApiKey


# ── TTS Config sub-models ──────────────────────────
class CartesiaTTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["cartesia"] = "cartesia"  # discriminator field
    voice_id: str = Field(..., min_length=1, max_length=100, description="Cartesia voice ID")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="Cartesia API key (optional, falls back to system key)")
    language: str = Field("en", max_length=10, description="BCP-47 language code for the input text (default: en). Only affects pronunciation; set to the caller's language when known.")
    # Numeric only. The preset strings ("slow"/"normal"/"fast") belong to Cartesia's older
    # models; sonic-3 — which this platform pins — raises
    # `ValueError: speed must be a float for sonic-3` inside the plugin constructor. They
    # were accepted here and then blew up at call time, so they are rejected up front.
    speed: Optional[float] = Field(1.0, ge=0.0, le=3.0, description="Speaking speed as a numeric multiplier of normal, 0.0–3.0 (e.g. 1.5 = 50% faster). Preset strings are not supported on sonic-3.")
    volume: Optional[float] = Field(1.0, ge=0.0, le=3.0, description="Output volume where 1.0 is the default. Lower for a quieter agent, higher for louder.")
    emotion: Optional[str] = Field(None, max_length=40, description="Emotion control string (Sonic 3 only), e.g. 'excited', 'calm', 'sad'. See Cartesia docs for supported values.")
    pronunciation_dict_id: Optional[str] = Field(None, max_length=100, description="ID of a Cartesia pronunciation dictionary to apply. Sonic 3 models only.")


class SarvamTTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["sarvam"] = "sarvam"
    # Not a Literal: the roster is the plugin's (livekit.plugins.sarvam), which the API
    # container does not install, and it grows with each Bulbul release. Validated at call
    # time instead — see core/agents/stt/lang.py::validate_sarvam_speaker.
    speaker: str = Field(..., max_length=30, description="Sarvam speaker identifier, from the bulbul:v3 roster (shubh, ritu, rahul, pooja, amit, kavya, … — 30 in all; see docs/reference/models.md). The bulbul:v2 names (anushka, manisha, vidya, arya, abhilash, karun, hitesh) are not valid on v3 and stop the call at start.")
    # Default is None, not a language: the field is always serialized, so any concrete
    # default here would silently override the factory fallback ("en-IN", see
    # src/core/agents/tts/factory.py) for every assistant that omits it.
    target_language_code: Optional[str] = Field(None, max_length=10, description="BCP-47 language code for synthesized speech. Bulbul speaks 11 Indic codes and nothing else: bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, od-IN, pa-IN, ta-IN, te-IN. Note en-IN, not en-US — anything outside the list is rejected and falls back to en-IN. Defaults to en-IN when omitted.")
    # Ranges mirror Sarvam's own limits. temperature starts at 0.01, not 0.0, and the
    # sample rate is an enum on their side — a value in between (20000, say) is rejected
    # by the API, so it must not pass validation here.
    pace: float = Field(1.0, ge=0.3, le=3.0, description="Speaking pace multiplier, 0.3–3.0 (1.0 = normal; >1.0 faster).")
    speech_sample_rate: Literal[8000, 16000, 22050, 24000, 32000, 44100, 48000] = Field(24000, description="Output audio sample rate in Hz. Use 24000 for general voice agents and 8000 only for narrowband telephony.")
    temperature: float = Field(0.3, ge=0.01, le=2.0, description="TTS sampling temperature, 0.01–2.0. Lower is more stable. Applies to bulbul:v3.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="Sarvam API key (optional, falls back to system key). TTS only — user transcription uses assistant_stt_config.api_key.")


class ElevenLabsVoiceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice stability (0–1). Higher = more consistent, lower = more expressive.")
    similarity_boost: Optional[float] = Field(None, ge=0.0, le=1.0, description="How closely output matches the voice (0–1). Higher = more similar but may add artifacts.")
    style: Optional[float] = Field(None, ge=0.0, le=1.0, description="Style strength of the voice (0–1).")
    speed: Optional[float] = Field(None, ge=0.25, le=4.0, description="Speaking speed multiplier (0.25–4.0). Not a v3 knob: on eleven_v3 (the default model) it is dropped before the call with a log line — switch to eleven_multilingual_v2, eleven_turbo_v2_5 or eleven_flash_v2_5 to change speaking rate.")
    use_speaker_boost: Optional[bool] = Field(None, description="Boost speaker clarity and target-speaker similarity.")


class ElevenLabsTTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["elevenlabs"] = "elevenlabs"
    voice_id: str = Field(..., min_length=1, max_length=100, description="ElevenLabs voice ID")
    model: str = Field("eleven_v3", max_length=40, description="ElevenLabs TTS model: eleven_v3 (default), eleven_multilingual_v2, eleven_turbo_v2_5 or eleven_flash_v2_5.")
    voice_settings: Optional[ElevenLabsVoiceSettings] = Field(None, description="Voice settings (stability, similarity_boost, style, speed, use_speaker_boost). Applies to all models.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="ElevenLabs API key (optional, falls back to system key)")


class MistralTTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["mistral"] = "mistral"
    voice_id: str = Field(..., min_length=1, max_length=100, description="Mistral voice ID")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="Mistral API key (optional, falls back to system key)")


# Discriminated union type
TTSConfig = Annotated[
    Union[CartesiaTTSConfig, SarvamTTSConfig, ElevenLabsTTSConfig, MistralTTSConfig],
    Field(discriminator="type"),  # discriminated by type field in parent
]
