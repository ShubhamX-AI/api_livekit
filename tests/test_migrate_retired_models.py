"""The retired-model migration: which stored rows it rewrites, and to what."""

import unittest

from scripts.migrate_retired_models import REPLACEMENTS, replacement_fields
from src.core.model_support.capabilities import CASCADE_MODELS, REASONING_MODELS


class TestReplacementFields(unittest.TestCase):
    def test_a_cascade_model_is_moved(self):
        self.assertEqual(
            replacement_fields({"model": "gpt-5.1"}),
            {"assistant_llm_config.model": "gpt-6-sol"},
        )

    def test_a_duplex_backend_model_is_moved(self):
        self.assertEqual(
            replacement_fields({"model": "gpt-live-1", "backend_model": "gpt-5.4-nano"}),
            {"assistant_llm_config.backend_model": "gpt-6-luna"},
        )

    def test_minimal_effort_becomes_none(self):
        """GPT-6 refuses `minimal`; kept, every turn on the new model would fail."""
        self.assertEqual(
            replacement_fields({"model": "gpt-5.4-nano", "reasoning_effort": "minimal"}),
            {
                "assistant_llm_config.model": "gpt-6-luna",
                "assistant_llm_config.reasoning_effort": "none",
            },
        )

    def test_a_current_model_is_left_alone(self):
        self.assertEqual(replacement_fields({"model": "gpt-6-luna"}), {})
        self.assertEqual(replacement_fields({}), {})

    def test_the_retired_models_are_off_the_allowlist(self):
        self.assertEqual(set(REPLACEMENTS) & CASCADE_MODELS, set())

    def test_every_replacement_is_a_reasoning_model(self):
        """Reasoning to reasoning, so the stored knobs stay valid and duplex still accepts it."""
        self.assertLessEqual(set(REPLACEMENTS.values()), REASONING_MODELS)


if __name__ == "__main__":
    unittest.main()
