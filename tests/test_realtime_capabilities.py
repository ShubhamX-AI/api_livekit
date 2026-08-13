"""Which realtime models take the GA-only session fields.

`session.truncation` (retention_ratio + token_limits) belongs to the GA Realtime API. The
older gpt-4o-*realtime-preview models are still on the allowlist, and an unknown session
field is answered with an error event rather than ignored — the same shape of failure as
sending a cascade LLM a knob its model cannot read.
"""

import unittest
from types import SimpleNamespace

from src.api.models.api_schemas.config.llm_config import (
    OPENAI_REALTIME_MODELS,
    validate_mode_config,
)
from src.core.model_support.capabilities import (
    DEFAULT_GEMINI_LIVE_MODEL,
    DEFAULT_GEMINI_VOICE,
    GEMINI_LIVE_MODELS,
    GEMINI_NO_MIDSESSION_CONTENT_MODELS,
    GEMINI_VOICES,
    REALTIME_TRUNCATION_MODELS,
    realtime_supports_truncation,
)


class TestGeminiUserTranscription(unittest.TestCase):
    """Gemini realtime writes user transcripts because the plugin defaults them on.

    session.py deliberately passes no `input_audio_transcription` for Gemini — the plugin
    substitutes `AudioTranscriptionConfig()` when the argument is omitted, and passing None
    explicitly is what would turn transcripts off. This test exists because that is a plugin
    default we depend on, not a value we set: call records and the end-call webhook lose
    every user turn if a plugin bump flips it.
    """

    def test_the_plugin_enables_user_transcription_by_default(self):
        from livekit.plugins.google.beta import realtime as google_realtime

        model = google_realtime.RealtimeModel(
            model="gemini-3.1-flash-live-preview",
            voice="Puck",
            modalities=["AUDIO"],
            instructions="x",
            api_key="k",
        )
        self.assertIsNotNone(model._opts.input_audio_transcription)
        self.assertTrue(model.capabilities.user_transcription)


class TestRealtimeTruncationSupport(unittest.TestCase):
    def test_the_ga_line_takes_truncation(self):
        for model in ("gpt-realtime", "gpt-realtime-1.5", "gpt-realtime-mini"):
            with self.subTest(model=model):
                self.assertTrue(realtime_supports_truncation(model))

    def test_the_preview_line_does_not(self):
        for model in ("gpt-4o-realtime-preview", "gpt-4o-mini-realtime-preview"):
            with self.subTest(model=model):
                self.assertFalse(realtime_supports_truncation(model))

    def test_an_unknown_model_is_treated_as_unsupported(self):
        """Omitting an optional field is safe; sending one the session lacks is not."""
        self.assertFalse(realtime_supports_truncation("gpt-realtime-2027-whatever"))

    def test_every_truncation_model_is_actually_allowlisted(self):
        """A truncation model the API rejects is dead code that reads like coverage.

        It happened: `gpt-realtime-2` and `gpt-realtime-2025-08-28` were listed as
        truncation-capable while `OPENAI_REALTIME_MODELS` refused both, so neither entry could
        ever be reached. The sets are now derived from one another, and this asserts it.
        """
        self.assertEqual(REALTIME_TRUNCATION_MODELS - OPENAI_REALTIME_MODELS, set())


class TestGeminiLiveModelRules(unittest.TestCase):
    """Gemini has no /v1/models to ask, so the plugin's own Literal is the only gate."""

    def test_the_allowlist_matches_the_installed_plugin(self):
        """A model outside the plugin's Literal opens a socket the API then closes."""
        from livekit.plugins.google.realtime.api_proto import LiveAPIModels
        from typing import get_args

        self.assertEqual(GEMINI_LIVE_MODELS, set(get_args(LiveAPIModels)))

    def test_the_voice_roster_matches_the_installed_plugin(self):
        from livekit.plugins.google.realtime.api_proto import Voice
        from typing import get_args

        self.assertEqual(GEMINI_VOICES, set(get_args(Voice)))

    def test_the_default_live_model_is_allowlisted_and_keeps_generate_reply(self):
        """The default has to be the model where every feature works, not the newest one."""
        self.assertIn(DEFAULT_GEMINI_LIVE_MODEL, GEMINI_LIVE_MODELS)
        self.assertNotIn(DEFAULT_GEMINI_LIVE_MODEL, GEMINI_NO_MIDSESSION_CONTENT_MODELS)

    def test_the_default_voice_is_on_the_roster(self):
        self.assertIn(DEFAULT_GEMINI_VOICE, GEMINI_VOICES)

    def test_a_chat_model_is_rejected_in_realtime_mode(self):
        with self.assertRaises(ValueError) as ctx:
            validate_mode_config(
                "realtime",
                SimpleNamespace(provider="gemini", model="gemini-2.5-flash", voice=None),
                None,
            )
        self.assertIn("not a Gemini Live model", str(ctx.exception))

    def test_a_live_model_is_accepted(self):
        validate_mode_config(
            "realtime",
            SimpleNamespace(
                provider="gemini", model="gemini-3.1-flash-live-preview", voice="Puck"
            ),
            None,
        )

    def test_gemini_is_the_default_provider_so_its_models_are_checked_unprovided(self):
        with self.assertRaises(ValueError):
            validate_mode_config(
                "realtime",
                SimpleNamespace(provider=None, model="gpt-realtime", voice=None),
                None,
            )


class TestRealtimeVoiceRules(unittest.TestCase):
    """One `voice` field, two rosters with nothing in common."""

    def test_a_gemini_voice_under_openai_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            validate_mode_config(
                "realtime",
                SimpleNamespace(provider="openai", model="gpt-realtime", voice="Puck"),
                None,
            )
        self.assertIn("is a Gemini Live voice", str(ctx.exception))

    def test_an_openai_voice_under_gemini_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            validate_mode_config(
                "realtime",
                SimpleNamespace(
                    provider="gemini", model="gemini-3.1-flash-live-preview", voice="marin"
                ),
                None,
            )
        self.assertIn("not a Gemini Live voice", str(ctx.exception))

    def test_an_unknown_openai_voice_is_allowed_through(self):
        """OpenAI ships realtime voices without an SDK Literal — do not block a new one."""
        validate_mode_config(
            "realtime",
            SimpleNamespace(provider="openai", model="gpt-realtime", voice="cedar"),
            None,
        )

    def test_no_voice_is_always_fine(self):
        validate_mode_config(
            "realtime",
            SimpleNamespace(provider="openai", model="gpt-realtime", voice=None),
            None,
        )


if __name__ == "__main__":
    unittest.main()
