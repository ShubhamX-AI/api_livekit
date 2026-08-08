"""Secrets must never round-trip through error responses, and provider keys must fit."""

import unittest
from unittest.mock import patch

from src.core.agents.stt.factory import create_stt, resolve_stt
from src.core.providers.keys import redact_text, redact_validation_errors

LONG_KEY = "sk-" + "a" * 300  # longer than the old 100-char cap, inside the 500 cap


class TestRedactText(unittest.TestCase):
    def test_masks_key_prefixes(self):
        self.assertIn("sk-proj-****", redact_text("failed: sk-proj-abcdefghijklmnop"))
        self.assertIn("sk-ant-****", redact_text("sk-ant-api03-abcdefghijkl"))
        self.assertIn("AIza****", redact_text("AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"))

    def test_masks_bearer_tokens(self):
        self.assertEqual(redact_text("Authorization: Bearer abcdefgh"), "Authorization: '****' ****")
        self.assertIn("Bearer ****", redact_text("Bearer eyJhbGciOiJIUzI1NiJ9.tokenvalue"))

    def test_masks_secret_assignments(self):
        self.assertNotIn("secret", redact_text("api_key=supersecretvalue123"))
        self.assertNotIn("supersecretvalue123", redact_text("api_key=supersecretvalue123"))

    def test_masks_long_opaque_tokens(self):
        out = redact_text("token " + "A" * 40 + " more")
        self.assertNotIn("A" * 40, out)

    def test_plain_text_untouched(self):
        self.assertEqual(redact_text("assistant not found"), "assistant not found")
        self.assertEqual(redact_text(""), "")


class TestRedactValidationErrors(unittest.TestCase):
    def test_secret_field_input_masked(self):
        errors = [
            {
                "type": "string_too_long",
                "loc": ("body", "assistant_llm_config", "api_key"),
                "msg": "String should have at most 500 characters",
                "input": LONG_KEY,
                "ctx": {},
            }
        ]
        redacted = redact_validation_errors(errors)
        self.assertEqual(redacted[0]["input"], "****")
        self.assertNotIn("ctx", redacted[0])
        self.assertNotIn(LONG_KEY, str(redacted))

    def test_nested_dict_input_masked_by_key_name(self):
        errors = [
            {
                "type": "value_error",
                "loc": ("body", "assistant_tts_config"),
                "msg": "Value error",
                "input": {"voice_id": "v1", "api_key": LONG_KEY},
            }
        ]
        redacted = redact_validation_errors(errors)[0]["input"]
        self.assertEqual(redacted["api_key"], "****")
        self.assertEqual(redacted["voice_id"], "v1")

    def test_non_secret_field_left_alone(self):
        errors = [{"type": "string_too_long", "loc": ("body", "assistant_name"), "msg": "x", "input": "x"}]
        self.assertEqual(redact_validation_errors(errors)[0]["input"], "x")


class TestApiKeyLength(unittest.TestCase):
    def test_long_key_accepted_by_schema(self):
        import json

        from src.api.models.api_schemas import CreateAssistant

        payload = {
            "assistant_name": "test",
            "assistant_description": "desc",
            "assistant_prompt": "hello",
            "assistant_mode": "cascade",
            "assistant_tts_model": "cartesia",
            "assistant_tts_config": {"type": "cartesia", "voice_id": "v1", "api_key": "cfg-key"},
            "assistant_llm_config": {"provider": "openai", "model": "gpt-4.1", "api_key": LONG_KEY},
        }
        parsed = CreateAssistant.model_validate_json(json.dumps(payload))
        self.assertEqual(parsed.assistant_llm_config.api_key, LONG_KEY)

    def test_superhuman_overlong_key_rejected(self):
        from pydantic import ValidationError

        from src.api.models.api_schemas import CreateAssistant

        with self.assertRaises(ValidationError):
            CreateAssistant(
                assistant_name="test",
                assistant_description="desc",
                assistant_prompt="hello",
                assistant_mode="cascade",
                assistant_llm_config={"provider": "openai", "api_key": "sk-" + "x" * 600},
            )


def _assistant(**overrides):
    from types import SimpleNamespace

    base = {
        "assistant_id": "a1",
        "assistant_mode": "cascade",
        "assistant_stt_model": "elevenlabs",
        "assistant_stt_config": {"api_key": "config-key"},
        "assistant_preferred_languages": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestElevenLabsSystemKeyFallback(unittest.TestCase):
    def test_config_key_wins(self):
        stt = create_stt(_assistant())
        self.assertEqual(stt._opts.api_key, "config-key")

    def test_env_key_used_when_config_has_none(self):
        with patch("src.core.agents.stt.factory.settings.ELEVENLABS_API_KEY", "env-key"):
            stt = create_stt(_assistant(assistant_stt_config={"type": "elevenlabs"}))
        self.assertEqual(stt._opts.api_key, "env-key")

    def test_missing_key_resolves_to_native(self):
        with patch("src.core.agents.stt.factory.settings.ELEVENLABS_API_KEY", ""):
            provider, _ = resolve_stt(_assistant(assistant_stt_config={}))
        self.assertEqual(provider, "native")

    def test_factory_returns_none_without_key(self):
        with patch("src.core.agents.stt.factory.settings.ELEVENLABS_API_KEY", ""):
            result = create_stt(_assistant(assistant_stt_config={"type": "elevenlabs"}))
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()