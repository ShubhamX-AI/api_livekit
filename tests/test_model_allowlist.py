"""The allowlist checker itself — the tool that keeps the model lists honest.

`scripts/check_model_allowlist.py` is what stands between an operator and the worst failure
this platform has (an allowlisted model OpenAI will not serve, which 400s every LLM turn and
leaves the caller on a silent line). If the checker's own logic breaks, the lists rot again
without a signal, so its report shape is tested here rather than trusted.
"""

import unittest

from scripts.check_model_allowlist import build_report


class TestBuildReport(unittest.TestCase):
    def test_flags_allowlisted_models_the_account_cannot_serve(self):
        # An account that serves only the cascade default: everything else must be reported.
        report = build_report({"gpt-4.1"})
        missing = report["missing_from_openai"]["OPENAI_CASCADE_MODELS"]
        self.assertNotIn("gpt-4.1", missing)
        self.assertTrue(missing, "every other allowlisted cascade model should be missing")
        self.assertTrue(report["internal_drift"]["default_cascade_model_available"])

    def test_reports_clean_when_the_account_serves_every_allowlisted_model(self):
        from src.api.models.api_schemas.config.llm_config import (
            OPENAI_CASCADE_MODELS,
            OPENAI_REALTIME_MODELS,
        )
        from src.core.model_support.capabilities import REALTIME_TRUNCATION_MODELS

        available = (
            set(OPENAI_CASCADE_MODELS)
            | set(OPENAI_REALTIME_MODELS)
            | set(REALTIME_TRUNCATION_MODELS)
        )
        report = build_report(available)
        for name, models in report["missing_from_openai"].items():
            self.assertEqual(models, [], f"{name} should be fully servable here")

    def test_missing_default_cascade_model_is_reported(self):
        report = build_report({"gpt-4o"})
        self.assertFalse(report["internal_drift"]["default_cascade_model_available"])

    def test_audio_and_image_models_are_not_offered_as_chat_candidates(self):
        report = build_report({"whisper-1", "dall-e-3", "gpt-4o-mini-transcribe", "tts-1"})
        self.assertEqual(report["available_not_allowlisted"]["chat"], [])


if __name__ == "__main__":
    unittest.main()
