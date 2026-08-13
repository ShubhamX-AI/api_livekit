"""What each model and provider actually accepts, and how a request for it is shaped.

This package is the single answer to "can this configuration run?", and it is deliberately
**dependency-free**: no FastAPI, no `livekit-agents`, no Beanie. Both deployments import it and
neither has the other's dependencies — the control image (`Dockerfile.control`) has no
`livekit-agents`, the agent image (`Dockerfile.agent`) has no FastAPI. Anything added here has
to import cleanly into both, or the two halves of the platform start disagreeing about which
configurations are legal, which is exactly the failure this package exists to prevent.

Contents:

- `capabilities` — which models exist, and which generation knobs each one reads. Static, and
  never edited from memory: see `scripts/check_model_allowlist.py`.
- `openai_live` — the same question asked of OpenAI at config time, because only OpenAI knows
  what it still serves. Retirement is invisible to a static list.
- `payload` — the Responses request body the runtime will actually send, so a replay or a
  probe tests the real thing rather than an approximation of it.
- `tool_schema` — one tool document to one OpenAI function schema, including when `strict`
  has to be turned off.

Import from the submodules (`from src.core.model_support.capabilities import ...`). The names
below are re-exported for the few callers that want the package front door.
"""

from src.core.model_support.capabilities import (
    CASCADE_MODELS,
    CHAT_MODELS,
    DEFAULT_CASCADE_MODEL,
    DEFAULT_REALTIME_MODEL,
    GPT5_GENERATION,
    PLUGIN_INJECTS_REASONING,
    REALTIME_TRUNCATION_MODELS,
    REASONING_MODELS,
    REASONING_TOOL_INCOMPATIBLE,
    realtime_supports_truncation,
    unsupported_knob_reason,
)

__all__ = [
    "CASCADE_MODELS",
    "CHAT_MODELS",
    "DEFAULT_CASCADE_MODEL",
    "DEFAULT_REALTIME_MODEL",
    "GPT5_GENERATION",
    "PLUGIN_INJECTS_REASONING",
    "REALTIME_TRUNCATION_MODELS",
    "REASONING_MODELS",
    "REASONING_TOOL_INCOMPATIBLE",
    "realtime_supports_truncation",
    "unsupported_knob_reason",
]
