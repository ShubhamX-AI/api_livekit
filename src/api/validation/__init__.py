"""Request guards that need more than the request itself.

Pydantic covers what a single payload can be judged on. These do not fit there:

- rules that need the **stored row** (a PATCH naming one field can still make the assistant
  unrunnable — see `enforce_stored_mode_constraints`);
- rules that need a **network call** (only OpenAI knows which models it still serves and
  which knob values a model takes). Pydantic validators are synchronous, so a call there
  would block the event loop.

They live outside `routes/` because more than one route has to apply them: creating an
assistant, updating one, and attaching or detaching a tool can each land the same broken
combination. One implementation, three callers, no drift.
"""

from src.api.validation.assistant_guard import (
    effective_llm_config,
    effective_value,
    enforce_openai_config,
    enforce_provider_keys,
    enforce_stored_mode_constraints,
    enforce_tool_change,
    resolve_probe_tools,
    will_attach_tools,
)

__all__ = [
    "effective_llm_config",
    "effective_value",
    "enforce_openai_config",
    "enforce_provider_keys",
    "enforce_stored_mode_constraints",
    "enforce_tool_change",
    "resolve_probe_tools",
    "will_attach_tools",
]
