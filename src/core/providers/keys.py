"""Provider API keys: where they live in an assistant, and how they are hidden.

Reads return keys masked, and writes reject a masked value — otherwise a client
that GETs an assistant, edits one field and PATCHes the whole object back would
persist the mask as a real key, which then wins over the system key and 401s
mid-call.
"""

import re
from typing import Annotated, Optional

from pydantic import AfterValidator

SYSTEM_KEY_PLACEHOLDER = "Using System provided API Key"

# Substrings that make a dict key a secret regardless of the provider.
SECRET_KEY_HINTS = ("authorization", "token", "secret", "api-key", "apikey", "api_key", "password")

_MASK_PATTERN = re.compile(r".{4}\.\.\..{4}")


def reject_masked_key(value: Optional[str]) -> Optional[str]:
    """Refuse api_key values that came out of `mask_api_key`."""
    if isinstance(value, str) and (
        value in (SYSTEM_KEY_PLACEHOLDER, "****") or _MASK_PATTERN.fullmatch(value)
    ):
        raise ValueError(
            "api_key looks masked (as returned by GET /assistant/details). "
            "Send the real key, or omit the field to use the system key."
        )
    return value


# Type for every request-schema `api_key` field; carries only the mask check, so
# each config keeps its own field line and provider-specific description.
ProviderApiKey = Annotated[Optional[str], AfterValidator(reject_masked_key)]


def mask_api_key(config: dict) -> dict:
    """Mask the `api_key` in a provider config, announcing the system-key fallback."""
    if not config:
        return config
    masked_config = config.copy()
    key = masked_config.get("api_key")
    if not key:
        masked_config["api_key"] = SYSTEM_KEY_PLACEHOLDER
    elif len(key) > 8:
        masked_config["api_key"] = f"{key[:4]}...{key[-4:]}"
    else:
        masked_config["api_key"] = "****"
    return masked_config


def mask_assistant_keys(data: dict) -> dict:
    """Mask the provider keys on an assistant dict, in place.

    Native STT carries no key, so its config is left untouched rather than being
    told about a fallback key it never uses.
    """
    for field in ("assistant_tts_config", "assistant_stt_config", "assistant_llm_config"):
        config = data.get(field)
        if config and config.get("type") != "native":
            data[field] = mask_api_key(config)
    return data


def provider_key_or_system(
    config: Optional[dict],
    config_provider: Optional[str],
    needed_provider: str,
    system_key: Optional[str],
) -> Optional[str]:
    """Return the assistant's key only when it belongs to the provider being called.

    A key stored under one provider is worthless to another — handing a Google key
    to OpenAI 401s — so a mismatch falls back to the system key (see 6e77183).
    """
    key = (config or {}).get("api_key")
    if key and (config_provider or "").lower() == needed_provider:
        return key
    return system_key


def reject_masked_config(config: Optional[dict]) -> Optional[dict]:
    """Refuse a free-form config that still carries `****` from `mask_secret_values`.

    Same round-trip trap as `reject_masked_key`: storing the literal `****` as a
    webhook token makes the webhook fail on every call.
    """
    for key, value in (config or {}).items():
        if isinstance(value, dict):
            reject_masked_config(value)
        elif value == "****":
            raise ValueError(
                f"'{key}' is masked (as returned by GET /tool/details). "
                "Send the real value, or omit the field to keep the stored one."
            )
    return config


def mask_secret_values(config: Optional[dict]) -> Optional[dict]:
    """Mask secret-looking values in a free-form config (webhook headers, tokens).

    For configs with no fixed schema — tool execution configs and inbound webhook
    strategies. Keys are matched by name, so a URL or a method stays readable.
    """
    if not config:
        return config

    masked = {}
    for key, value in config.items():
        lowered = str(key).lower()
        if isinstance(value, dict):
            masked[key] = mask_secret_values(value)
        elif value and any(hint in lowered for hint in SECRET_KEY_HINTS):
            masked[key] = "****"
        else:
            masked[key] = value
    return masked
