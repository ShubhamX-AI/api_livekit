# Audio Library

## Overview

The audio library stores reusable audio clips that can be attached to assistants as a **prerecorded greeting**. Upload a file once, then reference it from one or more assistants by `audio_id`.

When an assistant has `assistant_greeting_audio.enabled=true` and a valid `audio_id`, the worker plays the stored clip as the opening line instead of generating one with the model. This skips LLM + TTS (pipeline) or realtime audio generation (realtime) for the greeting — cutting token cost and latency. Works in both modes.

## How uploads are processed

- **Any common audio format is accepted** (mp3, m4a, ogg, wav, …). The server transcodes the upload to **WAV 48 kHz mono** in-process using PyAV (bundled ffmpeg — no system binary, no subprocess).
- **Maximum length is 30 seconds.** Longer clips are rejected with `400`.
- The normalized WAV is stored in S3; metadata (including the spoken `transcript` and measured `duration_seconds`) is stored in MongoDB.

## Attaching to an assistant

Set `assistant_greeting_audio` on the assistant via [Create Assistant](../assistant/create.md) or [Update Assistant](../assistant/update.md):

```json
{ "assistant_greeting_audio": { "enabled": true, "audio_id": "<audio_id>" } }
```

`enabled` is the on/off switch (recorded audio vs model greeting); `audio_id` attaches a library asset. The assistant endpoints validate that the asset exists, is active, and is owned by the caller.

## Runtime fallback

The recorded greeting never breaks a call. If the asset is missing/inactive, or the download/decode fails at call time, the assistant falls back to the normal model-generated greeting. In realtime mode the greeting stays interruptible (the realtime model's server-side turn detection ignores non-interruptible playback).

## Endpoints

- [Upload Audio](upload.md)
- [List Audio](list.md)
- [Get Audio Details](get.md)
- [Delete Audio](delete.md)
