"""DB tool documents -> function-calling schemas.

The schema is what OpenAI validates, and it validates strictly: the Responses API defaults
function tools to `strict`, where every property must appear in `required` and every object
and array must be fully described. A schema that breaks either rule is answered with a 400,
which the plugin raises non-retryable on every LLM turn — the assistant answers the call and
never speaks. These tests pin the shape that avoids that.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from src.core.agents.tool_builder import _build_raw_schema


def make_tool(*params, name="lookup_weather"):
    return SimpleNamespace(
        tool_name=name,
        tool_description="Look up the weather",
        tool_parameters=list(params),
    )


def make_param(name, type="string", required=True, description=None, enum=None):
    return SimpleNamespace(
        name=name, type=type, required=required, description=description, enum=enum
    )


class TestBuildRawSchema(unittest.TestCase):
    def test_all_required_scalars_stay_strict(self):
        schema = _build_raw_schema(
            make_tool(make_param("city"), make_param("days", "number")), True
        )
        params = schema["parameters"]
        self.assertEqual(schema["name"], "lookup_weather")
        self.assertEqual(sorted(params["required"]), ["city", "days"])
        self.assertFalse(params["additionalProperties"])
        # No explicit strict key: the API default (strict) is correct for this shape.
        self.assertNotIn("strict", schema)

    def test_parameter_details_are_carried_over(self):
        schema = _build_raw_schema(
            make_tool(make_param("unit", description="c or f", enum=["c", "f"]))
        )
        prop = schema["parameters"]["properties"]["unit"]
        self.assertEqual(prop["type"], "string")
        self.assertEqual(prop["description"], "c or f")
        self.assertEqual(prop["enum"], ["c", "f"])

    def test_an_optional_parameter_turns_strict_off(self):
        """Strict demands every property in `required`. An optional one cannot be strict,
        so the tool says so instead of shipping a strict schema OpenAI rejects."""
        schema = _build_raw_schema(
            make_tool(make_param("city"), make_param("unit", required=False)), True
        )
        self.assertIs(schema["strict"], False)
        self.assertEqual(schema["parameters"]["required"], ["city"])

    def test_object_and_array_parameters_turn_strict_off(self):
        """The Tool document has no nested schema, so `items`/`properties` cannot be
        emitted — and strict mode requires them."""
        for param_type in ("object", "array"):
            with self.subTest(type=param_type):
                schema = _build_raw_schema(make_tool(make_param("payload", param_type)), True)
                self.assertIs(schema["strict"], False)

    def test_relaxing_strict_is_logged_with_the_reason(self):
        with mock.patch("src.core.agents.tool_builder.logger") as log:
            _build_raw_schema(make_tool(make_param("unit", required=False)), True)
        message = log.info.call_args[0][0]
        self.assertIn("lookup_weather", message)
        self.assertIn("unit", message)

    def test_no_strict_key_outside_cascade(self):
        """Pipeline and realtime talk to the Realtime API, whose function tool has no
        `strict` field — the key would ride into session.update as an unknown parameter,
        and that API errors on unknown parameters instead of ignoring them. The tool would
        be dropped or the session refused, i.e. the agent silently loses its tools.
        """
        for params in (
            [make_param("unit", required=False)],
            [make_param("payload", "object")],
            [make_param("city")],
        ):
            with self.subTest(params=params):
                self.assertNotIn("strict", _build_raw_schema(make_tool(*params)))

    def test_a_tool_name_over_the_openai_limit_is_rejected(self):
        """Skipping one tool beats a 400 that takes every other tool down with it. The API
        allows 100-character names (api_schemas/tools.py); OpenAI allows 64."""
        with self.assertRaises(ValueError):
            _build_raw_schema(make_tool(make_param("city"), name="a" * 65))

    def test_a_tool_with_no_parameters_is_strict(self):
        schema = _build_raw_schema(make_tool(), True)
        self.assertEqual(schema["parameters"]["properties"], {})
        self.assertEqual(schema["parameters"]["required"], [])
        self.assertNotIn("strict", schema)

    def test_the_realtime_tool_object_accepts_what_we_emit(self):
        """The realtime path validates our raw schema against OpenAI's own tool model and
        drops the tool when validation fails (realtime_model.py::_convert_tools_to_oai)."""
        from openai.types.realtime.realtime_function_tool import RealtimeFunctionTool

        schema = _build_raw_schema(
            make_tool(make_param("city"), make_param("unit", required=False))
        )
        tool = RealtimeFunctionTool.model_validate({**schema, "type": "function"})
        self.assertEqual(tool.name, "lookup_weather")
        self.assertFalse(hasattr(tool, "strict"))


if __name__ == "__main__":
    unittest.main()
