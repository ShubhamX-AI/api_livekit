import unittest

from src.core.db.usage_aggregations import (
    usage_by_model_pipeline,
    usage_totals_pipeline,
)


class TestUsageAggregations(unittest.TestCase):
    def test_by_model_groups_on_type_provider_model(self):
        pipeline = usage_by_model_pipeline({"user_email": "a@example.com"})
        group = pipeline[2]["$group"]["_id"]
        self.assertEqual(set(group), {"type", "provider", "model"})
        self.assertEqual(pipeline[1], {"$unwind": "$model_usage"})

    def test_summary_starts_with_match(self):
        pipeline = usage_totals_pipeline({"user_email": "a@example.com"})
        self.assertEqual(pipeline[0], {"$match": {"user_email": "a@example.com"}})
        self.assertEqual(pipeline[1]["$group"]["_id"], None)
        self.assertIn("total_estimated_cost_usd", pipeline[1]["$group"])

    def test_llm_totals_count_the_duplex_labels_too(self):
        group = usage_by_model_pipeline({})[2]["$group"]
        for key in ("total_llm_tokens", "total_llm_input_text_tokens", "total_llm_output_audio_tokens"):
            condition = group[key]["$sum"]["$cond"][0]["$in"]
            self.assertEqual(condition[1], ["llm_usage", "voice_llm_usage", "backend_llm_usage"])
        # Non-LLM totals keep matching only their own type.
        self.assertEqual(group["total_tts_characters"]["$sum"]["$cond"][0]["$in"][1], ["tts_usage"])

    def test_by_model_sums_entry_cost(self):
        pipeline = usage_by_model_pipeline({})
        self.assertEqual(
            pipeline[2]["$group"]["total_estimated_cost_usd"],
            {"$sum": {"$ifNull": ["$model_usage.estimated_cost_usd", 0]}},
        )
