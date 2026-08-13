"""The live model gate: does OpenAI still serve the model this assistant names?

The static allowlist cannot answer that. OpenAI retired three `*-chat-latest` aliases on
2026-06-19 and every assistant holding one kept passing validation, then answered calls with
silence — the Responses API 400s on every turn for a model it no longer serves, so the caller
hears nothing and no log line at create time ever said why.

These tests pin the three behaviours that matter: reject when absent, accept when present,
and — the one that keeps this from becoming an outage of its own — accept when OpenAI cannot
be reached at all.
"""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from src.api.validation.assistant_guard import enforce_openai_config
from src.core.model_support import openai_live


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def fake_client(result):
    """Patchable httpx.AsyncClient whose GET returns `result` (or raises it)."""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url, headers=None):
            if isinstance(result, Exception):
                raise result
            return result

        async def post(self, url, headers=None, json=None):
            if isinstance(result, Exception):
                raise result
            return result

    return FakeAsyncClient


def models_payload(*ids):
    return FakeResponse(200, {"data": [{"id": model_id} for model_id in ids]})


class TestUnavailableModelReason(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        openai_live.clear_cache()

    def tearDown(self):
        openai_live.clear_cache()

    async def _reason(self, result, model="gpt-4.1", api_key="sk-test-key"):
        with patch.object(openai_live.httpx, "AsyncClient", fake_client(result)):
            return await openai_live.unavailable_model_reason(model, api_key)

    async def test_model_the_account_serves_is_accepted(self):
        self.assertIsNone(await self._reason(models_payload("gpt-4.1", "gpt-5-mini")))

    async def test_retired_model_is_rejected_with_a_next_step(self):
        reason = await self._reason(
            models_payload("gpt-4.1"), model="gpt-5.2-chat-latest"
        )
        self.assertIsNotNone(reason)
        self.assertIn("retired", reason)
        self.assertIn("check_model_allowlist.py", reason)

    async def test_unreachable_openai_does_not_block_the_write(self):
        """An OpenAI outage must not make assistants un-editable."""
        self.assertIsNone(await self._reason(TimeoutError("network down"), model="gpt-4.1"))

    async def test_non_200_does_not_block_the_write(self):
        self.assertIsNone(
            await self._reason(FakeResponse(429, text="slow down"), model="gpt-4.1")
        )

    async def test_empty_model_list_is_treated_as_unknown_not_as_empty(self):
        self.assertIsNone(await self._reason(models_payload(), model="gpt-4.1"))

    async def test_no_model_named_means_nothing_to_check(self):
        self.assertIsNone(await self._reason(models_payload("gpt-4.1"), model=None))

    async def test_answer_is_cached_per_key(self):
        calls = []

        class CountingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            async def get(self, url, headers=None):
                calls.append(headers)
                return models_payload("gpt-4.1")

        with patch.object(openai_live.httpx, "AsyncClient", CountingClient):
            await openai_live.unavailable_model_reason("gpt-4.1", "sk-a")
            await openai_live.unavailable_model_reason("gpt-4.1", "sk-a")
            await openai_live.unavailable_model_reason("gpt-4.1", "sk-b")

        self.assertEqual(len(calls), 2, "one lookup per distinct key, then cached")


class TestEnforceLiveModelAvailability(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        openai_live.clear_cache()

    def tearDown(self):
        openai_live.clear_cache()

    async def test_cascade_default_model_is_checked_when_no_model_is_named(self):
        """An assistant with no `model` still runs one — gpt-4.1 — so it gets checked too."""
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason",
            AsyncMock(return_value="the OpenAI account for this key does not serve it."),
        ) as reason, self.assertRaises(HTTPException) as ctx:
            await enforce_openai_config(
                "cascade", {"api_key": "sk-x"}, status_code=422
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("gpt-4.1", ctx.exception.detail)
        self.assertEqual(reason.await_args.args[0], "gpt-4.1")

    async def test_realtime_default_model_is_checked_for_openai(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock(return_value=None)
        ) as reason:
            await enforce_openai_config(
                "realtime", {"provider": "openai"}, status_code=422
            )
        self.assertEqual(reason.await_args.args[0], "gpt-realtime-1.5")

    async def test_gemini_is_not_checked_over_http(self):
        """There is no /v1/models for Gemini; its Live ids are checked against the plugin."""
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock()
        ) as reason:
            await enforce_openai_config(
                "realtime",
                {"provider": "gemini", "model": "gemini-3.1-flash-live-preview"},
                status_code=422,
            )
        reason.assert_not_awaited()

    async def test_realtime_mode_defaults_to_gemini_and_is_skipped(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock()
        ) as reason:
            await enforce_openai_config("realtime", {}, status_code=422)
        reason.assert_not_awaited()

    async def test_update_path_reports_400_not_422(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason",
            AsyncMock(return_value="the OpenAI account for this key does not serve it."),
        ), self.assertRaises(HTTPException) as ctx:
            await enforce_openai_config(
                "cascade", {"model": "gpt-5.5"}, status_code=400
            )
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_api_key_in_the_config_is_never_echoed_back(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason",
            AsyncMock(return_value="sk-proj-should-not-appear serves nothing"),
        ), self.assertRaises(HTTPException) as ctx:
            await enforce_openai_config(
                "cascade",
                {"model": "gpt-5.5", "api_key": "sk-proj-should-not-appear"},
                status_code=400,
            )
        self.assertNotIn("sk-proj-should-not-appear", ctx.exception.detail)

    async def test_unknown_mode_is_not_checked(self):
        with patch(
            "src.api.validation.assistant_guard.unavailable_model_reason", AsyncMock()
        ) as reason:
            await enforce_openai_config(None, {"model": "gpt-4.1"}, status_code=422)
        reason.assert_not_awaited()


class TestRejectedConfigReason(unittest.IsolatedAsyncioTestCase):
    """The probe: OpenAI's own verdict on this exact request, at config time.

    This is the gate that replaces guessing about which `reasoning_effort` values a model
    takes or whether an account may use `service_tier: "flex"` — questions no local table can
    answer, and whose wrong answer is a call that connects and never speaks.
    """

    def setUp(self):
        openai_live.clear_cache()

    def tearDown(self):
        openai_live.clear_cache()

    async def _probe(self, result, config=None, **kwargs):
        with patch.object(openai_live.httpx, "AsyncClient", fake_client(result)):
            return await openai_live.rejected_config_reason(
                "gpt-5-mini", "sk-test-key", config or {}, **kwargs
            )

    async def test_accepted_request_is_not_a_reason(self):
        self.assertIsNone(await self._probe(FakeResponse(200, {"id": "resp_1"})))

    async def test_openai_error_message_and_param_are_surfaced_verbatim(self):
        """The whole point: the WebSocket frame says nothing, HTTPS names the parameter."""
        reason = await self._probe(
            FakeResponse(
                400,
                {
                    "error": {
                        "message": "Unsupported value: 'reasoning.effort' does not support "
                        "'none' with this model.",
                        "param": "reasoning.effort",
                    }
                },
            ),
            {"reasoning_effort": "none"},
        )
        self.assertIn("does not support 'none'", reason)
        self.assertIn("reasoning.effort", reason)

    async def test_422_is_also_treated_as_a_refusal(self):
        reason = await self._probe(
            FakeResponse(422, {"error": {"message": "bad shape"}}), {"verbosity": "low"}
        )
        self.assertIn("bad shape", reason)

    async def test_a_refusal_with_no_parameter_names_the_candidate_knobs(self):
        """The verified case: gpt-4.1-nano + service_tier 'flex' is refused with no `param`.

        OpenAI's message is then the same "check your inputs" the WebSocket gives, so quoting it
        alone leaves the operator exactly where they started. The knobs actually set are listed
        instead, service_tier first because its availability is per-model and per-account.
        """
        reason = await self._probe(
            FakeResponse(
                400,
                {
                    "error": {
                        "message": "There was an issue with your request. Please check your "
                        "inputs and try again"
                    }
                },
            ),
            {"temperature": 0.5, "service_tier": "flex", "tool_choice": "auto"},
        )
        self.assertIn("check your inputs", reason)
        self.assertIn("named no parameter", reason)
        # Ordered: service_tier is the usual answer, so it comes first.
        self.assertLess(reason.index("service_tier"), reason.index("temperature"))
        self.assertIn("replay_cascade_request.py", reason)

    async def test_a_named_parameter_is_quoted_without_the_candidate_list(self):
        reason = await self._probe(
            FakeResponse(
                400,
                {
                    "error": {
                        "message": "Unsupported value: 'reasoning.effort' does not support "
                        "'none' with this model.",
                        "param": "reasoning.effort",
                    }
                },
            ),
            {"reasoning_effort": "none"},
        )
        self.assertIn("param: reasoning.effort", reason)
        self.assertNotIn("named no parameter", reason)

    async def test_a_detail_free_refusal_with_no_knobs_set_points_at_the_tool_schemas(self):
        """Nothing to bisect means the request shape itself is wrong — usually a tool schema."""
        reason = await self._probe(
            FakeResponse(400, {"error": {"message": "There was an issue with your request."}}),
            {},
        )
        self.assertIn("tool", reason)
        self.assertIn("--show-payload", reason)

    async def test_401_does_not_block_the_write(self):
        """A bad key is the call's problem to report, not this gate's to guess at."""
        self.assertIsNone(await self._probe(FakeResponse(401, {"error": {"message": "no"}})))

    async def test_429_does_not_block_the_write(self):
        self.assertIsNone(await self._probe(FakeResponse(429, {})))

    async def test_5xx_does_not_block_the_write(self):
        self.assertIsNone(await self._probe(FakeResponse(503, {})))

    async def test_network_error_does_not_block_the_write(self):
        self.assertIsNone(await self._probe(TimeoutError("down")))

    async def test_no_key_means_no_probe(self):
        with patch.object(openai_live.settings, "OPENAI_API_KEY", ""), patch.object(
            openai_live.httpx, "AsyncClient", fake_client(TimeoutError())
        ):
            self.assertIsNone(await openai_live.rejected_config_reason("gpt-4.1", None, {}))

    async def test_verdict_is_cached_per_knob_combination(self):
        calls = []

        class CountingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            async def post(self, url, headers=None, json=None):
                calls.append(json)
                return FakeResponse(200, {"id": "resp_1"})

        with patch.object(openai_live.httpx, "AsyncClient", CountingClient):
            await openai_live.rejected_config_reason(
                "gpt-5-mini", "sk-a", {"reasoning_effort": "low"}
            )
            await openai_live.rejected_config_reason(
                "gpt-5-mini", "sk-a", {"reasoning_effort": "low"}
            )
            await openai_live.rejected_config_reason(
                "gpt-5-mini", "sk-a", {"reasoning_effort": "high"}
            )

        self.assertEqual(len(calls), 2, "one probe per distinct knob combination")

    async def test_the_probe_stores_nothing_and_stays_short(self):
        sent = {}

        class CapturingClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc_info):
                return False

            async def post(self, url, headers=None, json=None):
                sent.update(json)
                return FakeResponse(200, {"id": "resp_1"})

        with patch.object(openai_live.httpx, "AsyncClient", CapturingClient):
            await openai_live.rejected_config_reason("gpt-4.1", "sk-a", {})

        self.assertIs(sent["store"], False)
        self.assertEqual(sent["max_output_tokens"], 16)


class TestRetiredModelsAreOffTheAllowlist(unittest.TestCase):
    """The static half of the same guard — these five must never come back."""

    def test_retired_and_gateway_only_models_are_rejected(self):
        from src.api.models.api_schemas.config.llm_config import OPENAI_CASCADE_MODELS

        for model in (
            "gpt-5.1-chat-latest",  # retired 2026-06-19
            "gpt-5.2-chat-latest",  # retired 2026-06-19
            "gpt-5.3-chat-latest",  # retired 2026-06-19
            "chat-latest",  # LiveKit Inference gateway id, needs Cloud credentials
            "gpt-oss-120b",  # served by baseten / groq, not api.openai.com
        ):
            self.assertNotIn(model, OPENAI_CASCADE_MODELS)


if __name__ == "__main__":
    unittest.main()
