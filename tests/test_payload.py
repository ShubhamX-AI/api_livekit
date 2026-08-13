"""The Responses payload builder — the shape the probe and the replay both depend on.

If this drifts from what `openai.responses.LLM` actually sends, both of them start lying: the
probe clears a config that fails on a call, or refuses one that would have worked. The two
mappings worth pinning are the ones that are not top-level fields — `reasoning_effort` goes to
`reasoning.effort`, `verbosity` goes to `text.verbosity` — and the SDK's own habit of stripping
the sampling parameters for the gpt-5 generation before anything is sent.
"""

import unittest

from src.core.model_support.payload import (
    build_responses_payload,
    gated_knob_signature,
    strips_sampling_params,
)


class TestBuildResponsesPayload(unittest.TestCase):
    def test_reasoning_effort_is_nested_not_top_level(self):
        payload = build_responses_payload("gpt-5-mini", {"reasoning_effort": "low"})
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertNotIn("reasoning_effort", payload)

    def test_verbosity_is_nested_under_text(self):
        payload = build_responses_payload("gpt-5-mini", {"verbosity": "high"})
        self.assertEqual(payload["text"], {"verbosity": "high"})
        self.assertNotIn("verbosity", payload)

    def test_temperature_is_sent_for_a_chat_model(self):
        payload = build_responses_payload("gpt-4.1", {"temperature": 0.3})
        self.assertEqual(payload["temperature"], 0.3)

    def test_temperature_is_omitted_for_the_gpt5_generation(self):
        """The SDK strips it on the "gpt-5" prefix, so a payload carrying it is not the real one."""
        payload = build_responses_payload("gpt-5-mini", {"temperature": 0.3})
        self.assertNotIn("temperature", payload)

    def test_tool_knobs_are_omitted_without_tools(self):
        payload = build_responses_payload(
            "gpt-4.1", {"tool_choice": "required", "parallel_tool_calls": True}
        )
        self.assertNotIn("tool_choice", payload)
        self.assertNotIn("parallel_tool_calls", payload)
        self.assertNotIn("tools", payload)

    def test_tool_knobs_are_sent_with_tools(self):
        tool = {"type": "function", "name": "t", "description": "d", "parameters": {}}
        payload = build_responses_payload(
            "gpt-4.1",
            {"tool_choice": "required", "parallel_tool_calls": False},
            tools=[tool],
        )
        self.assertEqual(payload["tools"], [tool])
        self.assertEqual(payload["tool_choice"], "required")
        self.assertIs(payload["parallel_tool_calls"], False)

    def test_probe_defaults_store_nothing_and_stay_short(self):
        payload = build_responses_payload("gpt-4.1", {}, max_output_tokens=16)
        self.assertIs(payload["store"], False)
        self.assertEqual(payload["max_output_tokens"], 16)

    def test_configured_max_output_tokens_is_used_when_none_is_passed(self):
        payload = build_responses_payload(
            "gpt-4.1", {"max_output_tokens": 900}, max_output_tokens=None
        )
        self.assertEqual(payload["max_output_tokens"], 900)

    def test_empty_config_sends_only_the_essentials(self):
        payload = build_responses_payload("gpt-4.1", None)
        self.assertEqual(set(payload), {"model", "input", "store"})

    def test_strips_sampling_params_covers_the_reasoning_prefixes(self):
        for model in ("gpt-5", "gpt-5-mini", "gpt-5.6-sol", "o3", "o4-mini"):
            self.assertTrue(strips_sampling_params(model), model)
        for model in ("gpt-4.1", "gpt-4o-mini"):
            self.assertFalse(strips_sampling_params(model), model)


class TestGatedKnobSignature(unittest.TestCase):
    def test_same_effective_request_shares_one_signature(self):
        """Two assistants with the same effective request must cost one probe, not two."""
        a = gated_knob_signature("gpt-5-mini", {"reasoning_effort": "low"}, has_tools=False)
        b = gated_knob_signature(
            "gpt-5-mini", {"reasoning_effort": "low", "max_output_tokens": None}, has_tools=False
        )
        self.assertEqual(a, b)

    def test_a_stripped_knob_does_not_change_the_signature(self):
        with_temp = gated_knob_signature("gpt-5-mini", {"temperature": 0.5}, has_tools=False)
        without = gated_knob_signature("gpt-5-mini", {}, has_tools=False)
        self.assertEqual(with_temp, without)

    def test_tools_change_the_signature(self):
        self.assertNotEqual(
            gated_knob_signature("gpt-5.2", {"reasoning_effort": "low"}, has_tools=True),
            gated_knob_signature("gpt-5.2", {"reasoning_effort": "low"}, has_tools=False),
        )

    def test_model_changes_the_signature(self):
        self.assertNotEqual(
            gated_knob_signature("gpt-5-mini", {}, has_tools=False),
            gated_knob_signature("gpt-5-nano", {}, has_tools=False),
        )

    def test_tool_only_knobs_are_ignored_without_tools(self):
        self.assertEqual(
            gated_knob_signature("gpt-4.1", {"tool_choice": "auto"}, has_tools=False),
            gated_knob_signature("gpt-4.1", {}, has_tools=False),
        )


if __name__ == "__main__":
    unittest.main()
