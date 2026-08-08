from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Interaction Config sub-models ──────────────────
class AssistantInteractionConfigSchema(BaseModel):
    speaks_first: bool = Field(True, description="If True (default), assistant speaks first. If False, assistant stays silent and waits for the user to speak.")
    filler_words: bool = Field(False, description="Enable filler words while the user is speaking")
    silence_reprompts: bool = Field(False, description="Enable silence reprompts when the user stops responding")
    silence_reprompt_interval: float = Field(10.0, ge=1.0, le=60.0, description="Interval in seconds between silence reprompts")
    silence_max_reprompts: int = Field(2, ge=0, le=5, description="Maximum number of silence reprompts before ending the session")
    background_sound_enabled: bool = Field(True, description="Enable background ambience during the session")
    thinking_sound_enabled: bool = Field(True, description="Enable the typing-style thinking sound while the assistant is processing")
    allow_interruptions: bool = Field(False, description="Allow user to interrupt the assistant's initial greeting. Default False (interruptions blocked).")
    input_guard_window_sec: float = Field(3.0, ge=0.0, le=10.0, description="Seconds at the start of every agent reply during which caller audio is blanked. Blocks repeated 'Hello? Hello?' and short filler sounds ('um', 'uh') from cutting the agent off. Raise to reject more fillers; the caller also cannot genuinely interrupt within the window. 0 disables.")
    preferred_languages: Optional[List[str]] = Field(None, description="BCP-47 language codes the agent supports (e.g. ['hi-IN', 'en-US', 'ta-IN']). A hint for the transcription prompt only — it is never sent to a speech provider as a language parameter and never pins or disables auto-detect. To pin a language, set it on assistant_stt_config. Unset means no hint.")
    max_call_duration_minutes: Optional[float] = Field(None, gt=0, description="Hard ceiling on active-call duration in minutes. When reached, agent says a brief farewell then hangs up gracefully. Unset/null defaults to 30 minutes at runtime.")

    # STT moved out to assistant_stt_model / assistant_stt_config. Reject the retired
    # keys loudly — silently ignoring them would drop a caller's per-assistant Sarvam key.
    model_config = ConfigDict(extra="forbid")


class UpdateAssistantInteractionConfigSchema(BaseModel):
    speaks_first: Optional[bool] = Field(None, description="If True, assistant speaks first. If False, assistant waits for user.")
    filler_words: Optional[bool] = Field(None, description="Enable or disable filler words")
    silence_reprompts: Optional[bool] = Field(None, description="Enable or disable silence reprompts")
    silence_reprompt_interval: Optional[float] = Field(None, ge=1.0, le=60.0, description="Interval in seconds between silence reprompts")
    silence_max_reprompts: Optional[int] = Field(None, ge=0, le=5, description="Maximum number of silence reprompts before ending the session")
    background_sound_enabled: Optional[bool] = Field(None, description="Enable or disable background ambience")
    thinking_sound_enabled: Optional[bool] = Field(None, description="Enable or disable the typing-style thinking sound")
    allow_interruptions: Optional[bool] = Field(None, description="Enable or disable user interruptions during assistant's initial greeting")
    input_guard_window_sec: Optional[float] = Field(None, ge=0.0, le=10.0, description="Seconds at the start of every agent reply during which caller audio is blanked, blocking repeats and filler sounds. 0 disables.")
    preferred_languages: Optional[List[str]] = Field(None, description="BCP-47 language codes the agent supports (e.g. ['hi-IN', 'en-US', 'ta-IN']). A transcription-prompt hint only, never a speech-provider parameter. Pass empty list to clear.")
    max_call_duration_minutes: Optional[float] = Field(None, gt=0, description="Hard ceiling on active-call duration in minutes. Pass null/omit to use platform default (30 min).")

    model_config = ConfigDict(extra="forbid")  # see AssistantInteractionConfigSchema


# ── Greeting audio sub-models ──────────────────
class GreetingAudioSchema(BaseModel):
    enabled: bool = Field(False, description="If True, play the referenced audio asset as the greeting instead of generating it with the model.")
    audio_id: Optional[str] = Field(None, description="ID of an uploaded audio asset (see /audio) to play as the greeting.")


class UpdateGreetingAudioSchema(BaseModel):
    enabled: Optional[bool] = Field(None, description="Toggle the recorded greeting on or off.")
    audio_id: Optional[str] = Field(None, description="Attach a different audio asset, or null to detach.")
