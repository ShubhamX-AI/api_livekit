import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from src.api.models.api_schemas import (
    UpdateInboundContextStrategy,
    UpdateWebhookInboundContextStrategyConfigSchema,
    WebhookInboundContextStrategyConfigSchema,
)
from src.api.routes.inbound_context_strategy import merge_strategy_config
from src.core.agents.inbound_context import resolve_inbound_context


def _strategy(config, strategy_type="webhook"):
    return SimpleNamespace(
        strategy_id="s-1",
        strategy_name="CRM lookup",
        strategy_type=strategy_type,
        strategy_config=config,
    )


async def _resolve(config, strategy_type="webhook"):
    return await resolve_inbound_context(
        strategy=_strategy(config, strategy_type),
        assistant_id="a-1",
        assistant_name="Test",
        user_email="user@example.com",
        room_name="room-1",
        job_metadata={"call_type": "inbound", "caller_number": "+911234567890"},
    )


class TestResolveInboundContextConfigHandling(unittest.IsolatedAsyncioTestCase):
    """The stored config is free-form Mongo data; none of it may crash the call."""

    async def asyncSetUp(self):
        self._log_patch = patch(
            "src.core.agents.inbound_context._log_lookup", new_callable=AsyncMock
        )
        self.mock_log = self._log_patch.start()
        self.addCleanup(self._log_patch.stop)

    async def test_null_headers_does_not_raise(self):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=RuntimeError("network down")
            )
            result = await _resolve({"url": "https://example.com/x", "headers": None})
        self.assertIsNone(result)

    async def test_non_numeric_timeout_falls_back_to_default(self):
        captured = {}

        def record(*args, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("stop here")

        with patch("httpx.AsyncClient", side_effect=record):
            result = await _resolve(
                {"url": "https://example.com/x", "timeout_seconds": "abc"}
            )
        self.assertIsNone(result)
        self.assertEqual(captured["timeout"], 10.0)

    async def test_out_of_range_timeout_is_clamped(self):
        captured = {}

        def record(*args, **kwargs):
            captured.update(kwargs)
            raise RuntimeError("stop here")

        with patch("httpx.AsyncClient", side_effect=record):
            await _resolve({"url": "https://example.com/x", "timeout_seconds": 999})
        self.assertEqual(captured["timeout"], 10.0)

        captured.clear()
        with patch("httpx.AsyncClient", side_effect=record):
            await _resolve({"url": "https://example.com/x", "timeout_seconds": 0.01})
        self.assertEqual(captured["timeout"], 0.5)

    async def test_missing_url_is_logged(self):
        result = await _resolve({"headers": {}})
        self.assertIsNone(result)
        self.mock_log.assert_awaited_once()

    async def test_unsupported_strategy_type_is_logged(self):
        result = await _resolve({"url": "https://example.com/x"}, strategy_type="grpc")
        self.assertIsNone(result)
        self.mock_log.assert_awaited_once()


class TestResolveInboundContextResponseShape(unittest.IsolatedAsyncioTestCase):
    """The webhook's response shape is the placeholder path; no key is an envelope."""

    async def asyncSetUp(self):
        self._log_patch = patch(
            "src.core.agents.inbound_context._log_lookup", new_callable=AsyncMock
        )
        self.mock_log = self._log_patch.start()
        self.addCleanup(self._log_patch.stop)

    async def _resolve_returning(self, body):
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: body,
        )
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            return await _resolve({"url": "https://example.com/x"})

    async def test_flat_response_is_returned_as_is(self):
        # The case that used to be discarded outright: {{name}} is now reachable.
        result = await self._resolve_returning({"name": "John"})
        self.assertEqual(result, {"name": "John"})

    async def test_legacy_context_wrapper_is_kept_as_an_ordinary_key(self):
        # Existing webhooks keep working, and {{context.name}} still resolves,
        # because "context" is no longer unwrapped — it just nests naturally.
        body = {"context": {"name": "John"}}
        result = await self._resolve_returning(body)
        self.assertEqual(result, body)

    async def test_nested_response_is_returned_as_is(self):
        body = {"customer": {"name": "John", "plan": "Enterprise"}}
        result = await self._resolve_returning(body)
        self.assertEqual(result, body)

    async def test_empty_object_is_accepted(self):
        result = await self._resolve_returning({})
        self.assertEqual(result, {})

    async def test_non_object_responses_are_rejected(self):
        for body in ([{"name": "John"}], "John", 42, None):
            with self.subTest(body=body):
                self.assertIsNone(await self._resolve_returning(body))


class TestSuccessLogRecordsShapeNotValues(unittest.IsolatedAsyncioTestCase):
    """The context payload holds caller PII; the activity log gets shape only."""

    async def asyncSetUp(self):
        self._log_patch = patch(
            "src.core.agents.inbound_context._log_lookup", new_callable=AsyncMock
        )
        self.mock_log = self._log_patch.start()
        self.addCleanup(self._log_patch.stop)

    async def _log_for(self, body):
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=response
            )
            await _resolve({"url": "https://example.com/x"})
        return self.mock_log.await_args.kwargs

    async def test_nested_keys_are_flattened_into_dotted_paths(self):
        kwargs = await self._log_for(
            {"context": {"candidate_id": "abc", "recruiter": {"name": "Pratiksha"}}}
        )
        self.assertEqual(kwargs["status"], "success")
        self.assertEqual(
            kwargs["response_data"]["context_key_paths"],
            ["context.candidate_id", "context.recruiter.name"],
        )
        self.assertEqual(kwargs["response_data"]["context_size"], 2)

    async def test_no_payload_value_is_logged(self):
        kwargs = await self._log_for(
            {"context": {"candidate_first_name": "Subham", "phone": "+918697421450"}}
        )
        blob = repr(kwargs["response_data"])
        self.assertNotIn("Subham", blob)
        self.assertNotIn("918697421450", blob)

    async def test_list_records_one_marker_plus_first_element_shape(self):
        kwargs = await self._log_for(
            {"skills": [{"name": "python"}, {"name": "go"}], "tags": []}
        )
        self.assertEqual(
            kwargs["response_data"]["context_key_paths"],
            ["skills[]", "skills[0].name", "tags[]"],
        )

    async def test_empty_object_logs_no_paths(self):
        kwargs = await self._log_for({})
        self.assertEqual(kwargs["response_data"]["context_key_paths"], ["{}"])

    async def test_path_count_is_capped(self):
        kwargs = await self._log_for({f"k{i}": i for i in range(500)})
        self.assertEqual(len(kwargs["response_data"]["context_key_paths"]), 200)


class TestWebhookConfigValidation(unittest.TestCase):
    def test_masked_header_is_rejected(self):
        with self.assertRaises(ValidationError):
            WebhookInboundContextStrategyConfigSchema(
                url="https://example.com/x", headers={"Authorization": "****"}
            )

    def test_real_header_is_accepted(self):
        config = WebhookInboundContextStrategyConfigSchema(
            url="https://example.com/x", headers={"Authorization": "Bearer real-token"}
        )
        self.assertEqual(config.headers["Authorization"], "Bearer real-token")

    def test_public_urls_are_accepted(self):
        # Plain http is allowed on purpose: the SSRF guard is the host/IP block,
        # not the scheme, and customers already on http must stay editable.
        for url in ("https://example.com/x", "http://example.com/x"):
            with self.subTest(url=url):
                config = WebhookInboundContextStrategyConfigSchema(url=url)
                self.assertEqual(config.url, url)

    def test_unsafe_urls_are_rejected(self):
        for url in (
            "ftp://example.com/x",
            "https://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/latest/meta-data/",
            "https://127.0.0.1/x",
            "https://10.0.0.5/x",
            "https://192.168.1.10/x",
            "https://localhost/x",
            "https://metadata.google.internal/x",
        ):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                WebhookInboundContextStrategyConfigSchema(url=url)


class TestHeaderMerge(unittest.TestCase):
    """A PATCH carrying one header must not wipe the stored Authorization."""

    def setUp(self):
        self.stored = {
            "type": "webhook",
            "url": "https://example.com/x",
            "headers": {"Authorization": "Bearer a", "X-Tenant": "t1"},
            "timeout_seconds": 2.0,
        }

    def test_adding_a_header_keeps_the_others(self):
        merged = merge_strategy_config(self.stored, {"headers": {"X-New": "1"}})
        self.assertEqual(
            merged["headers"],
            {"Authorization": "Bearer a", "X-Tenant": "t1", "X-New": "1"},
        )

    def test_rotating_a_token_keeps_the_others(self):
        merged = merge_strategy_config(self.stored, {"headers": {"Authorization": "Bearer b"}})
        self.assertEqual(
            merged["headers"], {"Authorization": "Bearer b", "X-Tenant": "t1"}
        )

    def test_null_deletes_a_single_header(self):
        merged = merge_strategy_config(self.stored, {"headers": {"X-Tenant": None}})
        self.assertEqual(merged["headers"], {"Authorization": "Bearer a"})

    def test_non_header_keys_still_replace(self):
        merged = merge_strategy_config(self.stored, {"timeout_seconds": 5.0})
        self.assertEqual(merged["timeout_seconds"], 5.0)
        self.assertEqual(merged["url"], "https://example.com/x")
        self.assertEqual(merged["headers"], self.stored["headers"])

    def test_untouched_headers_survive_a_config_only_patch(self):
        merged = merge_strategy_config(self.stored, {"url": "https://example.com/v2"})
        self.assertEqual(merged["headers"], self.stored["headers"])

    def test_empty_stored_config_is_safe(self):
        merged = merge_strategy_config({}, {"headers": {"X-New": "1"}})
        self.assertEqual(merged["headers"], {"X-New": "1"})


class TestUpdateStrategyValidation(unittest.TestCase):
    def test_null_header_value_is_allowed_on_update(self):
        config = UpdateWebhookInboundContextStrategyConfigSchema(headers={"X-Gone": None})
        self.assertIsNone(config.headers["X-Gone"])

    def test_masked_header_still_rejected_on_update(self):
        with self.assertRaises(ValidationError):
            UpdateWebhookInboundContextStrategyConfigSchema(
                headers={"Authorization": "****"}
            )

    def test_explicit_nulls_are_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateInboundContextStrategy(strategy_type=None, strategy_config=None)

    def test_null_name_is_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateInboundContextStrategy(strategy_name=None)

    def test_type_without_config_is_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateInboundContextStrategy(strategy_type="webhook")

    def test_name_only_update_is_accepted(self):
        request = UpdateInboundContextStrategy(strategy_name="CRM lookup v2")
        self.assertEqual(request.strategy_name, "CRM lookup v2")

    def test_type_with_config_is_accepted(self):
        request = UpdateInboundContextStrategy(
            strategy_type="webhook",
            strategy_config={"url": "https://example.com/v2", "timeout_seconds": 3.0},
        )
        self.assertEqual(request.strategy_config.url, "https://example.com/v2")


if __name__ == "__main__":
    unittest.main()
