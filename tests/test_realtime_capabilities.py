"""Which realtime models take the GA-only session fields.

`session.truncation` (retention_ratio + token_limits) belongs to the GA Realtime API. The
older gpt-4o-*realtime-preview models are still on the allowlist, and an unknown session
field is answered with an error event rather than ignored — the same shape of failure as
sending a cascade LLM a knob its model cannot read.
"""

import unittest

from src.api.models.api_schemas.config.llm_config import OPENAI_REALTIME_MODELS
from src.core.agents.llm_capabilities import (
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
        """Otherwise the set names models the API would reject at create time anyway."""
        self.assertTrue(REALTIME_TRUNCATION_MODELS & OPENAI_REALTIME_MODELS)
        unknown = REALTIME_TRUNCATION_MODELS - OPENAI_REALTIME_MODELS
        # Newer GA IDs may be listed here before the allowlist catches up; they must at
        # least all be gpt-realtime line members, never chat or preview models.
        self.assertTrue(all(m.startswith("gpt-realtime") for m in unknown))


if __name__ == "__main__":
    unittest.main()
