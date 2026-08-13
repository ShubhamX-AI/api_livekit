"""Every check that decides whether an assistant configuration can actually run a call.

The failure this file exists to prevent has one shape and it is the worst one the platform
has: the configuration is accepted, the call connects, OpenAI rejects **every** LLM turn with
`APIStatusError: 'There was an issue with your request. Please check your inputs and try
again', status_code=-1`, and the caller listens to silence until they hang up. Nothing in the
request looked wrong, nothing in the logs names the cause, and the assistant looks configured.

Four gates, cheapest first:

1. **Pydantic** (`api_schemas/`) — shape, ranges, enums. Offline, per request.
2. **`validate_mode_config`** — the mode/provider/model/STT rule table. Offline; re-run here
   against the stored row merged with the PATCH, because most PATCHes do not resend the mode.
3. **`unavailable_model_reason`** — does the account still serve this model id? One cached
   `GET /v1/models`. No static list can answer this: OpenAI retired three `*-chat-latest`
   aliases on 2026-06-19 and every assistant holding one kept validating clean.
4. **`rejected_config_reason`** — will OpenAI accept this exact request? One short probe with
   the real knobs and the real tool schemas. This is what catches a `reasoning_effort` value
   the model does not take, a `service_tier` the account may not use, and a tool schema the
   Responses API refuses — none of which are knowable offline.

Gates 3 and 4 fail *open* on anything that is not a clear refusal (network error, 401, 429,
5xx). An OpenAI outage must not make assistants un-editable.
"""

from fastapi import HTTPException

from src.api.models.api_schemas import validate_mode_config
from src.core.config import settings
from src.core.db.db_schemas import Tool
from src.core.logger import logger
from src.core.model_support.capabilities import (
    DEFAULT_CASCADE_MODEL,
    DEFAULT_REALTIME_MODEL,
)
from src.core.model_support.openai_live import (
    rejected_config_reason,
    unavailable_model_reason,
)
from src.core.model_support.speech import STT_ENV_KEYS, TTS_ENV_KEYS
from src.core.model_support.tool_schema import (
    END_CALL_TOOL_SCHEMA,
    ToolNameTooLong,
    build_tool_schema,
)
from src.core.providers.keys import redact_text


def effective_value(assistant, update_data: dict, field: str):
    """This write's value for `field`: the PATCH's if it named it, else the stored row's.

    Key presence, not truthiness: a PATCH that sends a field as null is *clearing* it, and
    falling back to the stored value there would re-validate something the operator just
    removed. Every guard below judges the assistant the write will leave behind, so they all
    have to resolve fields the same way — three hand-rolled variants of this is how a new
    field ends up checked in one place and not the others.
    """
    if field in update_data:
        return update_data[field]
    return getattr(assistant, field, None)


def effective_llm_config(assistant, update_data: dict) -> dict:
    """The LLM config a PATCH will actually leave on the row.

    Request values win over stored ones key by key: a PATCH that changes only `model` must
    still be judged against the provider already there. Only the fields the rule table and the
    live checks read are returned — that is the whole set of things a mode switch can
    invalidate.
    """
    stored_llm = getattr(assistant, "assistant_llm_config", None) or {}
    if "assistant_llm_config" in update_data:
        # Already merged over the stored row by the caller (merge_llm_config), or explicitly
        # null to clear it — the realtime→pipeline switch does that. Either way what sits in
        # update_data is the complete config the write will store, so falling back to the row
        # here would resurrect a knob the operator just cleared with a null.
        stored_llm = {}
    requested_llm = update_data.get("assistant_llm_config") or {}

    def effective(key):
        # Same rule as effective_value(), one level down: these keys live inside a
        # subdocument rather than on the row, so the two dicts stand in for
        # (update_data, assistant).
        return requested_llm[key] if key in requested_llm else stored_llm.get(key)

    return {
        "provider": effective("provider"),
        "model": effective("model"),
        "api_key": effective("api_key"),
        # Read by the realtime voice rule: switching provider on an existing assistant has to
        # be judged against the voice already on the row, or a Gemini voice survives under
        # provider 'openai' and the session dies at connect time.
        "voice": effective("voice"),
        # The generation knobs are model-gated (see model_support.capabilities), so a PATCH
        # that changes only the model has to be judged against the knobs already on the row.
        "temperature": effective("temperature"),
        "max_output_tokens": effective("max_output_tokens"),
        "reasoning_effort": effective("reasoning_effort"),
        "verbosity": effective("verbosity"),
        "service_tier": effective("service_tier"),
        "tool_choice": effective("tool_choice"),
        "parallel_tool_calls": effective("parallel_tool_calls"),
    }


def will_attach_tools(assistant, update_data: dict | None = None) -> bool:
    """Whether the session will hand the LLM any function tools.

    Not cosmetic. It decides three things OpenAI cares about: whether `tool_choice:
    "required"` is legal, whether `gpt-5.2`/`gpt-5.4*` still accept `reasoning.effort`, and
    whether the plugin's own injected reasoning effort has to be cleared
    (`create_llm(has_tools=...)`).

    Knowable at config time because the assistant *declares* its tools: `tool_ids` on the row,
    plus the built-in `end_call` when `assistant_end_call_enabled` is set.
    """
    update_data = update_data or {}
    return bool(effective_value(assistant, update_data, "tool_ids")) or bool(
        effective_value(assistant, update_data, "assistant_end_call_enabled")
    )


async def resolve_probe_tools(
    assistant, update_data: dict | None = None, *, strict_schemas: bool
) -> list[dict]:
    """The OpenAI tool schemas this assistant's next call will send.

    Built with `build_tool_schema`, the same function the runtime uses, so the probe tests the
    real payload rather than a stand-in. A tool whose name is too long is skipped here exactly
    as the runtime skips it, or the probe would reject a configuration that in fact runs (minus
    that tool).

    `strict_schemas` is True for cascade only: `strict` means nothing to the Realtime API and
    an unknown key there is an error.
    """
    update_data = update_data or {}
    tool_ids = effective_value(assistant, update_data, "tool_ids") or []

    schemas: list[dict] = []
    if tool_ids:
        tool_docs = await Tool.find(
            {"tool_id": {"$in": list(tool_ids)}, "tool_is_active": True}
        ).to_list()
        for tool_doc in tool_docs:
            try:
                schema, _ = build_tool_schema(
                    tool_doc.tool_name,
                    tool_doc.tool_description,
                    tool_doc.tool_parameters,
                    strict_schemas=strict_schemas,
                )
            except ToolNameTooLong as e:
                logger.warning(
                    "Skipping tool %s in the OpenAI config probe: %s",
                    tool_doc.tool_id,
                    e,
                )
                continue
            schemas.append(schema)

    if effective_value(assistant, update_data, "assistant_end_call_enabled"):
        schemas.append(END_CALL_TOOL_SCHEMA)

    return schemas


async def enforce_openai_config(
    mode: str | None,
    llm_config: dict | None,
    *,
    status_code: int,
    tools: list[dict] | None = None,
    has_tools: bool = False,
) -> None:
    """Gates 3 and 4: is this model served, and will OpenAI accept this exact request?

    Gemini is skipped: there is no `/v1/models` equivalent and no cheap probe, so its Live
    model ids are checked against the installed plugin's own list instead
    (`validate_mode_config`).

    `status_code` is 422 on create — the request named the model — and 400 on update, where
    the offending value may have come from the stored row rather than this PATCH. Same
    convention as `enforce_stored_mode_constraints`.
    """
    if mode not in ("pipeline", "cascade", "realtime"):
        return

    llm_config = llm_config or {}
    default_provider = "gemini" if mode == "realtime" else "openai"
    provider = (llm_config.get("provider") or default_provider).lower()
    if provider != "openai":
        return

    default_model = DEFAULT_CASCADE_MODEL if mode == "cascade" else DEFAULT_REALTIME_MODEL
    model = llm_config.get("model") or default_model
    api_key = llm_config.get("api_key")

    reason = await unavailable_model_reason(model, api_key)
    if reason:
        raise HTTPException(
            status_code=status_code,
            detail=redact_text(
                f"assistant_llm_config.model '{model}' cannot be used — {reason}"
            ),
        )

    # The probe only makes sense for cascade: that is the mode whose turns go to the Responses
    # API. Pipeline and realtime drive the Realtime API, whose session shape a Responses call
    # says nothing about.
    if mode != "cascade":
        return

    rejection = await rejected_config_reason(
        model, api_key, llm_config, tools=tools, has_tools=has_tools
    )
    if rejection:
        raise HTTPException(
            status_code=status_code,
            detail=redact_text(
                f"OpenAI rejected this configuration for model '{model}': {rejection}. "
                "Stored as-is it would fail on every LLM turn, so the call would connect and "
                "the assistant would never speak. See docs/reference/troubleshooting.md."
            ),
        )


def enforce_provider_keys(
    mode: str | None,
    stt_model: str | None,
    stt_config: dict | None,
    tts_model: str | None,
    tts_config: dict | None,
    *,
    status_code: int,
) -> None:
    """Reject a provider that has no key to authenticate with.

    Each stage resolves `config.api_key or <VENDOR>_API_KEY` at call time and, finding neither,
    logs one line and ends the job — the caller hears a connect and then nothing. The stage that
    is missing a key is knowable here, so it is refused here.

    This assumes the API container sees the same provider keys as the worker, which is how the
    deployment is wired (all three services share one `.env`, see docker-compose.yml). If they
    are ever split, this check starts refusing configurations the worker could have run.

    Realtime mode is skipped for TTS: one model does STT, LLM and TTS, and
    `assistant_tts_model`/`assistant_tts_config` are ignored at runtime.
    """
    if mode not in ("pipeline", "cascade", "realtime"):
        return

    missing: list[str] = []

    # STT: only cascade builds a plugin STT of its own. In pipeline mode a keyless provider
    # degrades to the LLM's own transcription (resolve_stt) rather than failing, and realtime
    # ignores the field entirely — so neither is worth refusing.
    if mode == "cascade":
        provider = stt_model or "sarvam"
        env_var = STT_ENV_KEYS.get(provider)
        if env_var and not ((stt_config or {}).get("api_key") or getattr(settings, env_var, None)):
            missing.append(
                f"assistant_stt_config.api_key is required for STT provider '{provider}' — "
                f"the server has no {env_var} configured"
            )

    if mode in ("pipeline", "cascade") and tts_model:
        env_var = TTS_ENV_KEYS.get(tts_model)
        if env_var and not ((tts_config or {}).get("api_key") or getattr(settings, env_var, None)):
            missing.append(
                f"assistant_tts_config.api_key is required for TTS provider '{tts_model}' — "
                f"the server has no {env_var} configured"
            )

    if missing:
        raise HTTPException(
            status_code=status_code,
            detail=redact_text(
                "; ".join(missing)
                + ". Without a key the stage cannot start and the call would connect to "
                "silence."
            ),
        )


async def enforce_tool_change(assistant, tool_ids: list[str]) -> None:
    """Re-validate an assistant against the tool list it is about to have.

    Attaching or detaching a tool is a configuration change like any other, and it moves two
    rules that have nothing to do with tools themselves: `gpt-5.2`/`gpt-5.4*` stop accepting
    `reasoning.effort` once function tools are present, and `tool_choice: "required"` needs at
    least one tool to choose from. A tool schema the Responses API refuses is the third way
    this endpoint can silence an assistant.

    400 rather than 422: the request is well-formed, and what it collides with is the stored
    row.
    """
    update_data = {"tool_ids": list(tool_ids)}
    enforce_stored_mode_constraints(assistant, update_data, None)

    mode = getattr(assistant, "assistant_mode", None)
    await enforce_openai_config(
        mode,
        effective_llm_config(assistant, update_data),
        status_code=400,
        tools=await resolve_probe_tools(
            assistant, update_data, strict_schemas=mode == "cascade"
        ),
        has_tools=will_attach_tools(assistant, update_data),
    )


def enforce_stored_mode_constraints(assistant, update_data: dict, new_mode: str | None) -> None:
    """Gate 2 against the *effective* assistant: stored row merged with this PATCH.

    The schema validator can only see the request, and its rules fire only when the request
    names the mode — but most PATCHes touch a field or two without resending it. So the stored
    row has to be merged in and re-checked here. Without this the update is accepted and the
    assistant then fails to start with no signal at update time (create_llm/create_stt return
    None and the job just ends).

    The rule table itself lives in one place — `validate_mode_config()` — so the request path
    and this path can never drift apart.
    """
    effective_mode = new_mode or getattr(assistant, "assistant_mode", None)
    if effective_mode not in ("pipeline", "cascade", "realtime"):
        return

    from types import SimpleNamespace

    config = effective_llm_config(assistant, update_data)
    effective_stt = update_data.get("assistant_stt_model") or getattr(
        assistant, "assistant_stt_model", None
    )

    try:
        validate_mode_config(
            effective_mode,
            SimpleNamespace(**config),
            effective_stt,
            has_tools=will_attach_tools(assistant, update_data),
        )
    except ValueError as e:
        # 400 (not 422): the request itself is well-formed — it is the combination with what
        # is already stored that cannot run.
        raise HTTPException(status_code=400, detail=redact_text(str(e)))
