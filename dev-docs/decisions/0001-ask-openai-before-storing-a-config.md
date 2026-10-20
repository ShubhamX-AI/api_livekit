# 0001. Ask OpenAI whether it will run a config before storing it

- **Status:** Accepted
- **Date:** 2026-08

## Context

One failure caused most "the assistant is broken" reports. We call it **the silent call**:

1. The API accepts an assistant config.
2. A call connects.
3. OpenAI rejects **every** LLM turn.
4. The caller hears silence for the whole call.

The worker log gives nothing to act on. The runtime talks to OpenAI over a WebSocket, and over
that socket a rejection arrives as `status_code=-1` with no parameter name.

Static lists could not prevent it, for three reasons:

- OpenAI retires models on its own schedule. A stale allowlist entry looks exactly like a
  working one until the call goes silent.
- Some refusals depend on the *value* of a knob, not on the model: a `reasoning_effort` value a
  given model refuses, or a `service_tier` the account may not use. No table can know these.
- STT/TTS model ids and Sarvam speaker names were free strings, so a typo was stored and failed
  at job start.

## Decision

Close the silent call off at the API, in the order a request meets the checks:

1. **The cascade allowlist lost five ids.**
   - `gpt-5.1-chat-latest`, `gpt-5.2-chat-latest` and `gpt-5.3-chat-latest` were retired by
     OpenAI on 2026-06-19.
   - `chat-latest` is a LiveKit Inference gateway id, which needs LiveKit Cloud credentials.
   - `gpt-oss-120b` is served by baseten/groq, not by `api.openai.com`.
2. **Two new gates ask OpenAI**, both in `src/core/model_support/openai_live.py`:
   - Does the account still serve the model? (`unavailable_model_reason`, one cached
     `GET /v1/models`.)
   - Will OpenAI accept this exact request, meaning model + knobs + tool schemas?
     (`rejected_config_reason`, one short Responses probe.) This is what catches a
     `reasoning_effort` *value* a model refuses and a `service_tier` the account may not use.

   Both are cached per key. Both fail **open** on a network error, 401, 429 or 5xx, so an
   OpenAI outage does not make assistants un-editable.
3. **`tool_choice: "required"` needs a tool.** `POST /tool/attach` and `POST /tool/detach`
   re-run the whole guard, because attaching or detaching a tool moves both that rule and the
   `gpt-5.2`/`gpt-5.4*` reasoning-with-tools rule.
4. **STT/TTS model ids and Sarvam speakers are allowlisted** in
   `src/core/model_support/speech.py`. A provider with no API key at all (neither in the config
   nor in the environment) is refused instead of failing at job start.
5. **Gemini Live models and realtime voices are validated.** The Live API was a five-id set at
   the time, and the Gemini and OpenAI voice rosters share no names. The default model has since
   moved again: see [0005](0005-adopt-gemini-3.8-live.md).

Three scripts carry the diagnosis:

| Script | Question it answers |
|---|---|
| `scripts/check_model_allowlist.py` | Is our list still true for this key? |
| `scripts/audit_assistant_models.py` | Which stored rows are stale? |
| `scripts/replay_cascade_request.py <id> --bisect` | Why did OpenAI refuse? It replays over HTTPS, where the error has detail. |

## Consequences

- **Do not restore** any of the five removed ids, and **do not add a replacement from memory**.
  Run `uv run python scripts/check_model_allowlist.py` and add what the account actually serves.
- Create, update, `/tool/attach` and `/tool/detach` make up to two network calls to OpenAI.
  They are cached per key and fail open, so latency and outages stay bounded.
- Rows saved before these gates exist can still be stale. Find them with
  `uv run python scripts/audit_assistant_models.py`; `--apply` clears the model field so the
  assistant falls back to the default.
- Operator-facing version of this story: [troubleshooting](../../docs/reference/troubleshooting.md).
  How the gates fit together: [Validation and model support](../subsystems/validation-and-models.md).

## Where in the code

| What | File | Symbol |
|---|---|---|
| Model still served? | `src/core/model_support/openai_live.py` | `unavailable_model_reason`, `available_models` |
| Exact request accepted? | `src/core/model_support/openai_live.py` | `rejected_config_reason` |
| Runs both gates on create/update | `src/api/validation/assistant_guard.py` | `enforce_openai_config` |
| Re-runs the guard on tool changes | `src/api/validation/assistant_guard.py` | `enforce_tool_change` |
| Keyless provider refused | `src/api/validation/assistant_guard.py` | `enforce_provider_keys` |
| STT/TTS model and speaker sets | `src/core/model_support/speech.py` | `STT_MODELS_BY_PROVIDER`, `TTS_MODELS_BY_PROVIDER`, `unsupported_sarvam_speaker_reason` |
| Cascade model sets | `src/core/model_support/capabilities.py` | `REASONING_MODELS`, `CHAT_MODELS`, `CASCADE_MODELS` |
