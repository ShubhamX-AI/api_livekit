"""A stage with no key to authenticate with must be refused at config time.

`create_stt` / `create_tts` resolve `config.api_key or <VENDOR>_API_KEY`, and finding neither
they log one line and return None — the job ends, the caller hears a connect and then silence.
The stage that has no key is knowable when the assistant is saved, so it is refused there.

Assumes the API container sees the same provider keys as the worker, which is how the
deployment is wired: all three services share one `.env` (docker-compose.yml).
"""

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src.api.validation.assistant_guard import enforce_provider_keys
from src.core.config import settings


def no_keys():
    """Patch every provider key to empty, as a fresh server with no .env would have."""
    return patch.multiple(
        settings,
        SARVAM_API_KEY="",
        CARTESIA_API_KEY="",
        DEEPGRAM_API_KEY="",
        ELEVENLABS_API_KEY="",
        MISTRAL_API_KEY="",
        OPENAI_API_KEY="",
    )


class TestEnforceProviderKeys(unittest.TestCase):
    def test_cascade_stt_without_any_key_is_rejected(self):
        with no_keys(), self.assertRaises(HTTPException) as ctx:
            enforce_provider_keys("cascade", "deepgram", {}, None, None, status_code=422)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("DEEPGRAM_API_KEY", ctx.exception.detail)

    def test_a_per_assistant_key_satisfies_the_check(self):
        with no_keys():
            enforce_provider_keys(
                "cascade", "deepgram", {"api_key": "dg-123"}, None, None, status_code=422
            )

    def test_a_system_key_satisfies_the_check(self):
        with no_keys(), patch.object(settings, "DEEPGRAM_API_KEY", "dg-sys"):
            enforce_provider_keys("cascade", "deepgram", {}, None, None, status_code=422)

    def test_the_default_stt_provider_is_checked_when_none_is_named(self):
        """Unset means Sarvam, so an unset STT model is not an unchecked one."""
        with no_keys(), self.assertRaises(HTTPException) as ctx:
            enforce_provider_keys("cascade", None, None, None, None, status_code=422)
        self.assertIn("SARVAM_API_KEY", ctx.exception.detail)

    def test_tts_without_any_key_is_rejected(self):
        with no_keys(), self.assertRaises(HTTPException) as ctx:
            enforce_provider_keys(
                "pipeline", None, None, "cartesia", {"voice_id": "v"}, status_code=422
            )
        self.assertIn("CARTESIA_API_KEY", ctx.exception.detail)

    def test_both_stages_are_reported_together(self):
        """One request, one error listing everything wrong with it."""
        with no_keys(), self.assertRaises(HTTPException) as ctx:
            enforce_provider_keys("cascade", "elevenlabs", {}, "mistral", {}, status_code=422)
        self.assertIn("ELEVENLABS_API_KEY", ctx.exception.detail)
        self.assertIn("MISTRAL_API_KEY", ctx.exception.detail)

    def test_pipeline_stt_is_not_rejected_because_it_degrades_instead(self):
        """resolve_stt falls back to the LLM's own transcription — the call still runs."""
        with no_keys():
            enforce_provider_keys(
                "pipeline", "sarvam", {}, "cartesia", {"api_key": "c-1"}, status_code=422
            )

    def test_realtime_ignores_both_stages(self):
        """One model does STT, LLM and TTS; the stage fields are ignored at runtime."""
        with no_keys():
            enforce_provider_keys("realtime", "sarvam", {}, "cartesia", {}, status_code=422)

    def test_an_unknown_mode_is_not_checked(self):
        with no_keys():
            enforce_provider_keys(None, "deepgram", {}, "cartesia", {}, status_code=422)

    def test_the_key_is_never_echoed_back(self):
        with no_keys(), self.assertRaises(HTTPException) as ctx:
            enforce_provider_keys(
                "cascade",
                "deepgram",
                {},
                "cartesia",
                {"api_key": "sk-cartesia-secret-value-123456"},
                status_code=422,
            )
        self.assertNotIn("sk-cartesia-secret-value-123456", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
