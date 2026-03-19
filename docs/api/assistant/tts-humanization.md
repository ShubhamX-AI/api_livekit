# TTS Humanization Prompting

This section contains exact copy-paste versions of the humanization prompt source files.

!!! warning "Do Not Mix Humanization Templates"

    Use only one TTS humanization template at a time, matched to `assistant_tts_model`.
    Do not combine Sarvam, Cartesia, and ElevenLabs humanization rules in the same prompt.
    Mixing provider templates can produce invalid formatting/tags and may cause TTS synthesis errors.

## Exact Prompt Files

- [Sarvam Prompt (exact)](humanization/tts_humanification_sarvam.md)
- [Cartesia Prompt (exact)](humanization/tts_humanification_cartesia.md)
- [ElevenLabs Prompt (exact)](humanization/tts_humanificaiton_elevnlabs.md)

Each page is a direct markdown mirror of the corresponding Python file under `assets/humanization/`.
