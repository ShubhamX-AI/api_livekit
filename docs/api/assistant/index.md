# Assistants

## Overview

Assistants define voice agent behavior, prompt/instructions, interaction settings, optional tools, and optional end-call behavior.

Assistant execution supports two LLM modes:

- `pipeline`: OpenAI realtime handles STT+LLM and a separate TTS provider speaks output.
- `realtime`: Gemini realtime handles STT+LLM+TTS in one model.

Supported TTS providers for `pipeline` mode are `cartesia`, `sarvam`, `elevenlabs`, and `mistral`.

## Mode Rules

- `assistant_llm_mode="pipeline"` requires both `assistant_tts_model` and `assistant_tts_config`.
- `assistant_llm_mode="realtime"` requires `assistant_llm_config`.
- In `realtime` mode, `assistant_tts_model` and `assistant_tts_config` are ignored by runtime.

## Endpoints

- [Create Assistant](create.md)
- [List Assistants](list.md)
- [Get Assistant Details](get.md)
- [Update Assistant](update.md)
- [Delete Assistant](delete.md)
- [Get Call Logs](logs.md)
- [Using Placeholders](placeholders.md)
- [TTS Humanization Prompting Guide](tts-humanization.md)
- [Sarvam Prompt (Exact)](humanization/tts_humanification_sarvam.md)
- [Cartesia Prompt (Exact)](humanization/tts_humanification_cartesia.md)
- [ElevenLabs Prompt (Exact)](humanization/tts_humanification_elevenlabs.md)
