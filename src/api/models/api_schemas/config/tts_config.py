from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.core.model_support.speech import (
    SARVAM_V4_FLASH_ONLY_LANGUAGES,
    SARVAM_V4_FLASH_PACE,
    SARVAM_V4_FLASH_SAMPLE_RATES,
    models_reading,
    unread_elevenlabs_settings,
    unsupported_sarvam_speaker_reason,
    unsupported_speech_model_reason,
)
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
    model: Literal["bulbul:v3", "bulbul:v4-flash"] = Field("bulbul:v3", description="Sarvam TTS model: bulbul:v3 (default) or bulbul:v4-flash (faster, cheaper, its own speaker roster and tighter limits: pace 0.5–2.0, temperature up to 1.0, sample rate 8000/16000/22050/24000).")
    # Not a Literal: the rosters are long and differ per model. Checked against the chosen
    # model's roster in `_speaker_fits_the_model`, and again at call time against the
    # plugin's own list — see core/agents/stt/lang.py::validate_sarvam_speaker.
    speaker: str = Field(..., max_length=40, description="Sarvam speaker identifier from the chosen model's roster. bulbul:v3: shubh, ritu, rahul, pooja, amit, kavya, … (30 in all). bulbul:v4-flash: names that carry the language and style, such as shubh_hi_customer or simran_enhi_customer (224 in all). The two rosters share no names; see docs/reference/models.md.")
    # Default is None, not a language: the field is always serialized, so any concrete
    # default here would silently override the factory fallback ("en-IN", see
    # src/core/agents/tts/factory.py) for every assistant that omits it.
    target_language_code: Optional[str] = Field(None, max_length=10, description="BCP-47 language code for synthesized speech. Bulbul speaks 11 Indic codes and nothing else: bn-IN, en-IN, gu-IN, hi-IN, kn-IN, ml-IN, mr-IN, od-IN, pa-IN, ta-IN, te-IN. Note en-IN, not en-US. bulbul:v4-flash also speaks the 12 IN22 codes (as-IN, brx-IN, doi-IN, kok-IN, ks-IN, mai-IN, mni-IN, ne-IN, sa-IN, sat-IN, sd-IN, ur-IN); an IN22 code on bulbul:v3 is rejected. Any other code is logged at call time and replaced with en-IN. Defaults to en-IN when omitted.")
    # Ranges mirror Sarvam's own limits. temperature starts at 0.01, not 0.0, and the
    # sample rate is an enum on their side — a value in between (20000, say) is rejected
    # by the API, so it must not pass validation here.
    pace: float = Field(1.0, ge=0.3, le=3.0, description="Speaking pace multiplier, 0.3–3.0 on bulbul:v3 and 0.5–2.0 on bulbul:v4-flash (1.0 = normal; >1.0 faster).")
    speech_sample_rate: Literal[8000, 16000, 22050, 24000, 32000, 44100, 48000] = Field(24000, description="Output audio sample rate in Hz. Use 24000 for general voice agents and 8000 only for narrowband telephony. bulbul:v4-flash takes 8000, 16000, 22050 or 24000 only.")
    # None, not 0.3: a concrete default would be stored on every bulbul:v4-flash row, where
    # Sarvam ignores the value, and resending that row would then be refused.
    temperature: Optional[float] = Field(None, ge=0.01, le=2.0, description="TTS sampling temperature, 0.01–2.0 (lower is more stable). bulbul:v3 only; defaults to 0.3 when omitted. Rejected on bulbul:v4-flash, where Sarvam fixes it at 0.6 server-side.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="Sarvam API key (optional, falls back to system key). TTS only — user transcription uses assistant_stt_config.api_key.")

    @model_validator(mode="after")
    def _speaker_fits_the_model(self):
        """Rejected here, not just at call time.

        The Sarvam plugin raises on a speaker its model cannot use, and that exception escapes
        create_tts and entrypoint(): the job dies with a traceback and the caller hears
        nothing. `create_tts` still checks (rows predate this validator), but a new assistant
        cannot be saved with a speaker that would do that.
        """
        reason = unsupported_sarvam_speaker_reason(self.speaker, self.model)
        if reason:
            raise ValueError(f"{reason}. See docs/reference/models.md.")
        return self

    @model_validator(mode="after")
    def _knobs_fit_v4_flash(self):
        """bulbul:v4-flash is stricter than v3, and the field bounds above are v3's. It is also
        the only model that speaks the IN22 languages.

        Outside these limits the plugin clamps or raises, and Sarvam refuses a sample rate
        the v4 stream does not take — so the value is rejected while it can still be fixed.
        Temperature is refused outright: Sarvam ignores it on v4-flash.
        """
        if self.model != "bulbul:v4-flash":
            if self.target_language_code in SARVAM_V4_FLASH_ONLY_LANGUAGES:
                raise ValueError(
                    f"target_language_code {self.target_language_code!r} is an IN22 code, "
                    "spoken by bulbul:v4-flash only — set model to 'bulbul:v4-flash'"
                )
            return self
        low, high = SARVAM_V4_FLASH_PACE
        if not low <= self.pace <= high:
            raise ValueError(f"pace must be between {low} and {high} on bulbul:v4-flash")
        if self.temperature is not None:
            raise ValueError(
                "bulbul:v4-flash does not read temperature (Sarvam fixes it at 0.6) — remove it"
            )
        if self.speech_sample_rate not in SARVAM_V4_FLASH_SAMPLE_RATES:
            rates = ", ".join(str(rate) for rate in sorted(SARVAM_V4_FLASH_SAMPLE_RATES))
            raise ValueError(f"speech_sample_rate must be one of {rates} on bulbul:v4-flash")
        return self


class ElevenLabsVoiceSettings(BaseModel):
    """Which model reads which setting: ELEVENLABS_UNREAD_SETTINGS in
    src/core/model_support/speech.py, enforced by ElevenLabsTTSConfig below."""

    model_config = ConfigDict(extra="forbid")

    stability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice stability (0–1). Higher = more consistent, lower = more expressive. Every model reads it; on eleven_v3 it acts as three modes: 0.0 creative, 0.5 natural, 1.0 robust.")
    similarity_boost: Optional[float] = Field(None, ge=0.0, le=1.0, description="How closely output matches the voice (0–1). Higher = more similar but may add artifacts. Rejected on eleven_v3 and eleven_v3_conversational, which do not read it.")
    style: Optional[float] = Field(None, ge=0.0, le=1.0, description="Style strength of the voice (0–1). Only eleven_multilingual_v2 reads it; rejected on every other model.")
    speed: Optional[float] = Field(None, ge=0.25, le=4.0, description="Speaking speed multiplier (0.25–4.0). Read by eleven_multilingual_v2, eleven_turbo_v2_5 and eleven_flash_v2_5 (and their _v2 versions); rejected on eleven_v3 (the default), eleven_v3_conversational, eleven_v4 and eleven_v4_turbo.")
    use_speaker_boost: Optional[bool] = Field(None, description="Boost speaker clarity and target-speaker similarity. Only eleven_multilingual_v2 and eleven_v3_conversational read it; rejected on every other model.")


class ElevenLabsTTSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["elevenlabs"] = "elevenlabs"
    voice_id: str = Field(..., min_length=1, max_length=100, description="ElevenLabs voice ID")
    model: str = Field("eleven_v3", max_length=40, description="ElevenLabs TTS model: eleven_v3 (default), eleven_v3_conversational, eleven_v4, eleven_v4_turbo, eleven_multilingual_v2, eleven_turbo_v2_5 or eleven_flash_v2_5 (also eleven_turbo_v2, eleven_flash_v2).")
    voice_settings: Optional[ElevenLabsVoiceSettings] = Field(None, description="Voice settings (stability, similarity_boost, style, speed, use_speaker_boost). Each model reads only some of them, and a setting the chosen model does not read is rejected. eleven_v3 (the default) reads stability only; eleven_multilingual_v2 reads all five. See docs/reference/models.md.")
    api_key: ProviderApiKey = Field(None, min_length=1, max_length=500, description="ElevenLabs API key (optional, falls back to system key)")

    @field_validator("model", mode="after")
    @classmethod
    def _model_is_real(cls, value):
        """A misspelled model id used to reach the vendor and fail every synthesis."""
        reason = unsupported_speech_model_reason("elevenlabs", value, stage="tts")
        if reason:
            raise ValueError(f"{reason}. See docs/reference/models.md.")
        return value

    @model_validator(mode="after")
    def _settings_fit_the_model(self):
        """ElevenLabs accepts a setting its model ignores, so it is refused here instead.

        Stored, it would look like it was shaping the voice while doing nothing.
        """
        settings = self.voice_settings.model_dump() if self.voice_settings else {}
        unread = unread_elevenlabs_settings(self.model, settings)
        if unread:
            readers = "; ".join(f"{k}: {', '.join(models_reading(k))}" for k in unread)
            raise ValueError(
                f"{self.model} does not read voice_settings {', '.join(unread)}. Remove "
                f"{'it' if len(unread) == 1 else 'them'}, or pick a model that reads "
                f"{'it' if len(unread) == 1 else 'them'} ({readers}). "
                "See docs/reference/models.md."
            )
        return self


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
