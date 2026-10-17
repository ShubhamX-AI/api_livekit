"""Duplex mode: OpenAI GPT-Live as a fourth assistant mode.

GPT-Live listens while it speaks and hands reasoning and tool calls to a backend Responses
model. The rules below are what keep a duplex assistant from being stored in a shape the
worker cannot run: a model or voice from another mode, a knob the backend rejects, or a
feature that needs `session.say()` (GPT-Live has no TTS to say anything with).
"""

import unittest
from decimal import Decimal
from types import SimpleNamespace
from typing import get_args
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from src.api.models.api_schemas import CreateAssistant, UpdateAssistant
from src.api.routes.assistant import update_assistant
from src.api.validation import enforce_openai_config, enforce_stored_mode_constraints
from src.core.db.db_schemas import AssistantInteractionConfig, GreetingAudioConfig
from src.core.model_support.capabilities import GPT_LIVE_VOICES
from src.core.pricing import price_model_usage

BASE = {
    "assistant_name": "A",
    "assistant_description": "d",
    "assistant_prompt": "You are a helpful voice assistant.",
    "assistant_mode": "duplex",
}


class QueryField:
    def __eq__(self, other):
        return other


class TestDuplexSchema(unittest.TestCase):
    def test_a_bare_duplex_assistant_is_accepted(self):
        """No TTS, no STT, no llm_config: every duplex default is a runnable one."""
        created = CreateAssistant(**BASE)
        self.assertEqual(created.assistant_mode, "duplex")
        self.assertIsNone(created.assistant_tts_model)

    def test_the_full_duplex_config_is_accepted(self):
        created = CreateAssistant(
            **BASE,
            assistant_llm_config={
                "provider": "openai",
                "model": "gpt-live-1",
                "voice": "cedar",
                "backend_model": "gpt-6-luna",
                "backend_instructions": "Look things up with the tools.",
                "reasoning_effort": "low",
                "verbosity": "low",
                "service_tier": "flex",
                "tool_choice": "auto",
            },
        )
        self.assertEqual(created.assistant_llm_config.backend_model, "gpt-6-luna")

    def test_configs_the_worker_cannot_run_are_rejected(self):
        bad = {
            "a Gemini provider": {"provider": "gemini"},
            "a realtime model": {"model": "gpt-realtime-1.5"},
            "a removed voice": {"voice": "aster"},
            "a Gemini voice": {"voice": "Puck"},
            "a chat model as backend": {"backend_model": "gpt-4.1"},
            "temperature on a reasoning backend": {"temperature": 0.5},
            "temperature on the default backend": {"backend_model": None, "temperature": 0.5},
        }
        for label, llm_config in bad.items():
            with self.subTest(label), self.assertRaises(ValidationError):
                CreateAssistant(**BASE, assistant_llm_config=llm_config)

    def test_greeting_audio_is_rejected(self):
        """GPT-Live cannot play a recording; `session.say()` raises without a TTS."""
        with self.assertRaises(ValidationError) as ctx:
            CreateAssistant(
                **BASE, assistant_greeting_audio={"enabled": True, "audio_id": "a1"}
            )
        self.assertIn("assistant_greeting_audio", str(ctx.exception))

    def test_a_disabled_or_empty_greeting_is_fine(self):
        CreateAssistant(**BASE, assistant_greeting_audio={"enabled": False, "audio_id": "a1"})
        CreateAssistant(**BASE, assistant_greeting_audio={"enabled": True, "audio_id": None})

    def test_filler_words_are_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            CreateAssistant(**BASE, assistant_interaction_config={"filler_words": True})
        self.assertIn("filler_words", str(ctx.exception))

    def test_backend_fields_are_rejected_outside_duplex(self):
        for field, value in (("backend_model", "gpt-6-luna"), ("backend_instructions", "x")):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                CreateAssistant(
                    **{**BASE, "assistant_mode": "pipeline"},
                    assistant_tts_model="cartesia",
                    assistant_tts_config={"voice_id": "v1"},
                    assistant_llm_config={field: value},
                )

    def test_an_update_to_duplex_with_filler_words_is_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(
                assistant_mode="duplex", assistant_interaction_config={"filler_words": True}
            )

    def test_the_voice_set_matches_the_plugin(self):
        from livekit.plugins.openai.realtime import GPTLiveVoices

        self.assertEqual(GPT_LIVE_VOICES, set(get_args(GPTLiveVoices)))


def stored_assistant(**fields):
    defaults = {
        "assistant_mode": "duplex",
        "assistant_llm_config": None,
        "assistant_stt_model": None,
        "assistant_tts_model": None,
        "assistant_interaction_config": AssistantInteractionConfig(),
        "assistant_greeting_audio": GreetingAudioConfig(),
        "tool_ids": [],
        "assistant_end_call_enabled": False,
    }
    return SimpleNamespace(**{**defaults, **fields})


class TestMaxOutputTokens(unittest.TestCase):
    def test_below_the_api_minimum_is_rejected(self):
        """OpenAI refuses fewer than 16, and the save-time probe always sends 16 itself."""
        with self.assertRaises(ValidationError):
            CreateAssistant(**BASE, assistant_llm_config={"max_output_tokens": 15})
        CreateAssistant(**BASE, assistant_llm_config={"max_output_tokens": 16})


class TestDuplexStoredRow(unittest.TestCase):
    """Most PATCHes do not resend the mode, so the stored row has to be judged too."""

    def test_switching_to_duplex_with_a_stored_greeting_is_refused(self):
        assistant = stored_assistant(
            assistant_mode="pipeline",
            assistant_greeting_audio=GreetingAudioConfig(enabled=True, audio_id="a1"),
        )
        with self.assertRaises(HTTPException) as ctx:
            enforce_stored_mode_constraints(assistant, {"assistant_mode": "duplex"}, "duplex")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("assistant_greeting_audio", ctx.exception.detail)

    def test_turning_on_filler_words_on_a_duplex_assistant_is_refused(self):
        update = {"assistant_interaction_config": {"filler_words": True}}
        with self.assertRaises(HTTPException):
            enforce_stored_mode_constraints(stored_assistant(), update, None)

    def test_turning_on_the_greeting_on_a_duplex_assistant_is_refused(self):
        update = {"assistant_greeting_audio": {"enabled": True, "audio_id": "a1"}}
        with self.assertRaises(HTTPException):
            enforce_stored_mode_constraints(stored_assistant(), update, None)

    def test_a_stored_knob_is_judged_against_the_new_backend(self):
        assistant = stored_assistant(
            assistant_llm_config={"backend_model": "gpt-6-luna", "reasoning_effort": "low"}
        )
        update = {"assistant_llm_config": {"backend_model": "gpt-5.2", "reasoning_effort": "low"}}
        # gpt-5.2 refuses reasoning.effort once tools are attached; end_call is a tool.
        assistant.assistant_end_call_enabled = True
        with self.assertRaises(HTTPException):
            enforce_stored_mode_constraints(assistant, update, None)


class TestDuplexUpdateRoute(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for target in (
            "src.api.validation.assistant_guard.unavailable_model_reason",
            "src.api.validation.assistant_guard.rejected_config_reason",
        ):
            patcher = patch(target, AsyncMock(return_value=None))
            self.addCleanup(patcher.stop)
            patcher.start()

    async def _update(self, assistant, request):
        assistant.update = AsyncMock()
        assistant_model = SimpleNamespace(
            assistant_id=QueryField(),
            assistant_created_by_email=QueryField(),
            find_one=AsyncMock(return_value=assistant),
        )
        with patch("src.api.routes.assistant.Assistant", assistant_model):
            await update_assistant(
                assistant_id="assistant-1",
                request=request,
                current_user=SimpleNamespace(user_email="user@example.com"),
            )
        return assistant.update.await_args.args[0]["$set"]

    async def test_switching_into_duplex_drops_the_stored_realtime_model(self):
        """`gpt-realtime-1.5` is not a GPT-Live model; carrying it over would 400 the switch."""
        written = await self._update(
            stored_assistant(
                assistant_mode="pipeline",
                assistant_llm_config={"model": "gpt-realtime-1.5", "api_key": "sk-x-12345678"},
                assistant_tts_model="cartesia",
            ),
            UpdateAssistant(assistant_mode="duplex"),
        )
        self.assertIsNone(written["assistant_llm_config"])

    async def test_switching_out_of_duplex_uses_only_the_new_config(self):
        written = await self._update(
            stored_assistant(
                assistant_llm_config={"model": "gpt-live-1", "voice": "cedar", "backend_model": "gpt-6-sol"},
                assistant_tts_model="cartesia",
            ),
            UpdateAssistant(assistant_mode="cascade", assistant_llm_config={"model": "gpt-4.1"}),
        )
        self.assertEqual(written["assistant_llm_config"], {"model": "gpt-4.1"})

    async def test_a_patch_within_duplex_still_merges(self):
        written = await self._update(
            stored_assistant(assistant_llm_config={"voice": "cedar", "backend_model": "gpt-6-sol"}),
            UpdateAssistant(assistant_llm_config={"verbosity": "low"}),
        )
        self.assertEqual(
            written["assistant_llm_config"],
            {"voice": "cedar", "backend_model": "gpt-6-sol", "verbosity": "low"},
        )


class TestDuplexLiveChecks(unittest.IsolatedAsyncioTestCase):
    async def test_both_models_are_checked_and_the_backend_is_probed(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock(return_value=None)
        ) as served, patch(
            "src.api.validation.assistant_guard.rejected_config_reason", AsyncMock(return_value=None)
        ) as probe:
            await enforce_openai_config(
                "duplex", {"backend_model": "gpt-6-luna", "verbosity": "low"}, status_code=422
            )
        self.assertEqual(
            [call.args[0] for call in served.await_args_list], ["gpt-live-1", "gpt-6-luna"]
        )
        self.assertEqual(probe.await_args.args[0], "gpt-6-luna")

    async def test_the_default_backend_is_checked_when_none_is_named(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock(return_value=None)
        ), patch(
            "src.api.validation.assistant_guard.rejected_config_reason", AsyncMock(return_value=None)
        ) as probe:
            await enforce_openai_config("duplex", {}, status_code=422)
        self.assertEqual(probe.await_args.args[0], "gpt-5.6-luna")

    async def test_an_unserved_backend_names_the_field(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason",
            AsyncMock(side_effect=[None, "the OpenAI account for this key does not serve it."]),
        ), self.assertRaises(HTTPException) as ctx:
            await enforce_openai_config("duplex", {"backend_model": "gpt-6-sol"}, status_code=400)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("backend_model 'gpt-6-sol'", ctx.exception.detail)

    async def test_a_backend_refusal_becomes_the_error(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock(return_value=None)
        ), patch(
            "src.api.validation.assistant_guard.rejected_config_reason",
            AsyncMock(return_value="Unsupported value: 'minimal'"),
        ), self.assertRaises(HTTPException) as ctx:
            await enforce_openai_config("duplex", {"reasoning_effort": "minimal"}, status_code=422)
        self.assertIn("minimal", ctx.exception.detail)


class TestDuplexWebCall(unittest.IsolatedAsyncioTestCase):
    async def test_text_only_is_refused(self):
        """GPT-Live has no text modality, so a text-only chat has nothing to run on."""
        from src.api.models.api_schemas import TriggerWebCall
        from src.api.routes import web_call

        assistant_model = SimpleNamespace(
            assistant_id=QueryField(),
            assistant_created_by_email=QueryField(),
            find_one=AsyncMock(return_value=SimpleNamespace(assistant_mode="duplex")),
        )
        with patch.object(web_call, "Assistant", assistant_model), self.assertRaises(
            HTTPException
        ) as ctx:
            await web_call.get_token(
                TriggerWebCall(assistant_id="a1", text_only=True),
                current_user=SimpleNamespace(user_email="user@example.com"),
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("duplex", ctx.exception.detail)


class TestDuplexPricing(unittest.TestCase):
    def test_the_voice_model_is_billed_per_second_and_the_backend_per_token(self):
        result = price_model_usage(
            [
                {"type": "llm_usage", "provider": "openai", "model": "gpt-live-1", "session_duration": 120},
                {
                    "type": "llm_usage",
                    "provider": "openai",
                    # OpenAI names the snapshot that served the backend, not the alias.
                    "model": "gpt-6-luna-2026-09-30",
                    "input_tokens": 1_000_000,
                    "output_tokens": 1_000_000,
                },
            ]
        )
        self.assertTrue(result.pricing_complete)
        # $0.05/min for two minutes, plus $0.10 in and $0.50 out per 1M tokens.
        self.assertEqual(result.estimated_cost_usd, Decimal("0.10") + Decimal("0.10") + Decimal("0.50"))

    def test_an_older_snapshot_is_not_priced_as_its_alias(self):
        """`gpt-4o-2024-05-13` has its own list price; guessing gpt-4o's would hide that."""
        result = price_model_usage(
            [{"type": "llm_usage", "provider": "openai", "model": "gpt-4o-2024-05-13", "input_tokens": 10}]
        )
        self.assertFalse(result.pricing_complete)

    def test_session_seconds_cost_nothing_on_a_token_billed_model(self):
        """Realtime models report session_duration too; it must not be charged on them."""
        result = price_model_usage(
            [{"type": "llm_usage", "provider": "openai", "model": "gpt-realtime-1.5", "session_duration": 600}]
        )
        self.assertEqual(result.estimated_cost_usd, Decimal(0))
        self.assertTrue(result.pricing_complete)


class TestCreateGPTLive(unittest.TestCase):
    """The worker half: what GPTLiveModel is built with from a stored row."""

    def _build(self, has_tools=False, **llm_config):
        from src.core.agents.llm import create_gpt_live

        return create_gpt_live(
            SimpleNamespace(
                assistant_id="assistant-1",
                assistant_llm_config={"api_key": "sk-test", **llm_config},
            ),
            has_tools=has_tools,
        )

    def test_defaults(self):
        opts = self._build()._opts
        self.assertEqual(opts.model, "gpt-live-1")
        self.assertEqual(opts.voice, "marin")
        self.assertEqual(opts.delegation, "responses")
        self.assertEqual(opts.responses["model"], "gpt-5.6-luna")
        # The backend always gets instructions: without them it does not know its answers
        # are read out loud.
        self.assertIn("read out", opts.responses["instructions"])

    def test_backend_knobs_take_the_responses_shape(self):
        opts = self._build(
            voice="cedar",
            backend_model="gpt-6-sol",
            backend_instructions="Use the order tools.",
            reasoning_effort="low",
            verbosity="low",
            service_tier="priority",
            tool_choice="auto",
            parallel_tool_calls=False,
            max_output_tokens=256,
        )._opts
        self.assertEqual(opts.voice, "cedar")
        self.assertEqual(
            opts.responses,
            {
                "model": "gpt-6-sol",
                "instructions": "Use the order tools.",
                "reasoning": {"effort": "low"},
                "text": {"verbosity": "low"},
                "service_tier": "priority",
                "tool_choice": "auto",
                "parallel_tool_calls": False,
                "max_output_tokens": 256,
            },
        )

    def test_a_knob_the_backend_rejects_is_dropped_not_sent(self):
        """A stale knob fails every delegated turn, so it is dropped with a warning."""
        with patch("src.core.agents.llm.factory.logger") as log:
            opts = self._build(has_tools=True, backend_model="gpt-5.2", reasoning_effort="low")._opts
        self.assertNotIn("reasoning", opts.responses)
        self.assertIn("reasoning_effort", log.warning.call_args[0][0])

    def test_no_key_anywhere_builds_nothing(self):
        from src.core.agents.llm import create_gpt_live

        with patch("src.core.agents.llm.factory.settings.OPENAI_API_KEY", ""), patch(
            "src.core.agents.llm.factory.logger"
        ):
            self.assertIsNone(
                create_gpt_live(SimpleNamespace(assistant_id="a", assistant_llm_config={}))
            )


if __name__ == "__main__":
    unittest.main()
