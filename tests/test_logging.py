"""Logging fixes from the 2026-10-17 logging audit (L-01, L-02, L-03, L-05, L-06, L-09)."""

import asyncio
import io
import json
import logging
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.logger import JsonFormatter, _RedactingFilter
from src.core.providers.keys import redact_log_text, redact_text

OPENAI_KEY = "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789"
OPAQUE_KEY = "Zx9Qw8Er7Ty6Ui5Op4As3Df2Gh1Jk0LmNbVcXz"  # 38 chars, no vendor prefix
QUEUE_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
UUID_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


class TestRedactLogText(unittest.TestCase):
    def test_masks_vendor_key(self):
        self.assertNotIn(OPENAI_KEY, redact_log_text(f"bad key {OPENAI_KEY}"))

    def test_masks_opaque_long_token(self):
        self.assertNotIn(OPAQUE_KEY, redact_log_text(f"input_value='{OPAQUE_KEY}'"))

    def test_masks_url_credentials(self):
        out = redact_log_text(
            "cannot reach mongodb://admin:secretpassword@db:27017/app"
        )
        self.assertNotIn("secretpassword", out)
        self.assertIn("mongodb://****@db:27017/app", out)

    def test_masks_url_credentials_without_user(self):
        self.assertNotIn("hunter2pw", redact_log_text("redis://:hunter2pw@cache:6379"))

    def test_trace_ids_survive(self):
        line = (
            f"queue_id={QUEUE_ID} assistant {UUID_ID} room=sip-bridge-{UUID_ID} "
            f"call {UUID_ID.upper()} branch=z9hG4bK-{QUEUE_ID}"
        )
        self.assertEqual(redact_log_text(line), line)

    def test_hex_secrets_longer_than_an_id_are_masked(self):
        # Shapes a hex-id allowance must not let through.
        for secret in (
            "a" * 40,  # Deepgram key
            "sk_" + "b" * 48,  # ElevenLabs key
            "c" * 64,  # HMAC / signature
            UUID_ID + OPAQUE_KEY[:20],  # id with an opaque token glued on
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, redact_log_text(f"value {secret}"))

    def test_http_redaction_unchanged(self):
        # HTTP bodies keep masking every 32+ char token, ids included.
        self.assertNotIn(QUEUE_ID, redact_text(f"queue {QUEUE_ID}"))


def _record(msg, *args, exc_info=None):
    return logging.LogRecord("app", logging.ERROR, __file__, 1, msg, args, exc_info)


def _raised(message):
    try:
        raise ValueError(message)
    except ValueError:
        return sys.exc_info()


class TestRedactingFilter(unittest.TestCase):
    def test_masks_traceback_in_json_output(self):
        record = _record("boom", exc_info=_raised(f"api_key={OPAQUE_KEY}"))
        _RedactingFilter().filter(record)
        entry = json.loads(JsonFormatter().format(record))
        self.assertIn("ValueError", entry["exception"])
        self.assertNotIn(OPAQUE_KEY, entry["exception"])

    def test_masks_traceback_in_text_output(self):
        record = _record("boom", exc_info=_raised(OPENAI_KEY))
        _RedactingFilter().filter(record)
        self.assertNotIn(OPENAI_KEY, logging.Formatter().format(record))

    def test_formatter_that_rerenders_exc_info_sees_masked_text(self):
        # LiveKit's CLI JSON formatter calls formatException(exc_info) itself when it is set.
        record = _record("boom", exc_info=_raised(OPENAI_KEY))
        _RedactingFilter().filter(record)
        self.assertIsNone(record.exc_info)
        self.assertIn(OPENAI_KEY[:8], record.exc_text)  # prefix kept, rest masked
        self.assertNotIn(OPENAI_KEY, record.exc_text)

    def test_bad_args_left_for_handle_error(self):
        record = _record("%d items", "not-a-number")
        self.assertTrue(_RedactingFilter().filter(record))
        self.assertEqual(record.args, ("not-a-number",))

    def test_end_to_end_through_a_handler(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(_RedactingFilter())
        log = logging.getLogger("test_logging.e2e")
        log.addHandler(handler)
        log.propagate = False
        try:
            log.error("queue %s key %s", QUEUE_ID, OPENAI_KEY)
        finally:
            log.removeHandler(handler)
        self.assertIn(QUEUE_ID, stream.getvalue())
        self.assertNotIn(OPENAI_KEY, stream.getvalue())

    def test_json_carries_pid(self):
        entry = json.loads(JsonFormatter().format(_record("x")))
        self.assertIsInstance(entry["pid"], int)


class TestDatabaseConnectLine(unittest.IsolatedAsyncioTestCase):
    async def test_connect_line_has_no_credentials(self):
        from src.core.db import database

        client = MagicMock()
        client.admin.command = AsyncMock()
        url = "mongodb://admin:secretpassword@db.internal:27017/?authSource=admin"
        with (
            patch.object(database.settings, "MONGODB_URL", url),
            patch.object(database, "AsyncMongoClient", return_value=client),
            patch.object(database, "init_beanie", AsyncMock()),
            patch.object(database.Database, "client", None),
            self.assertLogs(database.logger, logging.INFO) as logs,
        ):
            await database.Database.connect_db()
        output = "\n".join(logs.output)
        self.assertIn("db.internal:27017", output)
        self.assertNotIn("secretpassword", output)
        self.assertNotIn("admin:", output)


class TestBridgeProcessLogging(unittest.TestCase):
    """Bridge processes must configure logging themselves (L-01) and tag the room (L-02)."""

    def tearDown(self):
        from src.core import logger as logger_module

        logger_module.clear_room_context()

    def test_outbound_entry_configures_logging_and_room(self):
        from src.core import logger as logger_module
        from src.services.exotel.custom_sip_reach import bridge

        seen_room = []

        async def fake_run_bridge(**kwargs):
            seen_room.append(logger_module._current_room)

        with (
            patch.object(bridge, "setup_logging") as setup,
            patch.object(bridge, "run_bridge", fake_run_bridge),
        ):
            bridge._bridge_subprocess_entry(
                "+910000000000", "room-out-1", {}, None, 10000, "call-1", None
            )
        setup.assert_called_once()
        self.assertEqual(seen_room, ["room-out-1"])

    def test_inbound_entry_configures_logging(self):
        from src.services.exotel.custom_sip_reach import inbound_worker

        with (
            patch.object(inbound_worker, "setup_logging") as setup,
            patch.object(inbound_worker, "_run_inbound_bridge", AsyncMock()),
        ):
            inbound_worker.inbound_bridge_subprocess_entry(
                "room-in-1", 10000, "127.0.0.1", 20000, 8, "token", None, None, None
            )
        setup.assert_called_once()


class TestDispatcherLoopSurvives(unittest.IsolatedAsyncioTestCase):
    """A failing pass is logged and the loop carries on (L-05)."""

    async def _run_loop(self, *, startup_error=None):
        from src.services.outbound_dispatcher import dispatcher

        wake = MagicMock()
        wake.wait = AsyncMock()
        # Tick 1 fails like a MongoDB outage; tick 2 stops the test via cancellation.
        recover = AsyncMock(
            side_effect=[RuntimeError("mongo down"), asyncio.CancelledError()]
        )
        with (
            patch.object(dispatcher, "_new_call_event", wake),
            patch.object(
                dispatcher,
                "_fail_stale_calls_on_startup",
                AsyncMock(side_effect=startup_error),
            ),
            patch.object(dispatcher, "_process_pending", AsyncMock()),
            patch.object(dispatcher, "_recover_stuck_dispatching", recover),
            patch.object(dispatcher, "_watch_for_new_calls", AsyncMock()),
            patch.object(dispatcher, "_watch_for_call_completions", AsyncMock()),
            patch.object(dispatcher, "_orphan_reaper_loop", AsyncMock()),
            self.assertLogs(dispatcher.logger, logging.ERROR) as logs,
            self.assertRaises(asyncio.CancelledError),
        ):
            await dispatcher.outbound_dispatcher_loop()
        return recover, logs

    async def test_failed_tick_is_logged_and_retried(self):
        recover, logs = await self._run_loop()
        self.assertEqual(recover.await_count, 2)
        self.assertIn("Dispatcher tick failed", logs.output[0])
        self.assertIsNotNone(logs.records[0].exc_info)

    async def test_failed_startup_pass_does_not_stop_dispatch(self):
        recover, logs = await self._run_loop(startup_error=RuntimeError("mongo down"))
        self.assertEqual(recover.await_count, 2)
        self.assertIn("Dispatcher startup pass failed", logs.output[0])

    async def test_exit_callback_logs_a_crashed_task(self):
        from src.services.outbound_dispatcher import dispatcher

        async def crash():
            raise RuntimeError("boom")

        task = asyncio.create_task(crash())
        await asyncio.gather(task, return_exceptions=True)
        with self.assertLogs(dispatcher.logger, logging.CRITICAL):
            dispatcher.log_dispatcher_exit(task)

    async def test_exit_callback_quiet_on_cancel(self):
        from src.services.outbound_dispatcher import dispatcher

        task = asyncio.create_task(asyncio.sleep(10))
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        with self.assertNoLogs(dispatcher.logger):
            dispatcher.log_dispatcher_exit(task)


class TestSipListenerBindFailure(unittest.IsolatedAsyncioTestCase):
    """A bind failure keeps its traceback, and stops the dedicated dispatcher (L-06)."""

    def _patches(self):
        from src.services.exotel.custom_sip_reach import inbound_listener

        bind_error = AsyncMock(side_effect=OSError(98, "Address already in use"))
        return inbound_listener, (
            patch.object(inbound_listener, "INBOUND_SIP_LISTEN", True),
            patch.object(inbound_listener, "_inbound_server", None),
            patch.object(inbound_listener.asyncio, "start_server", bind_error),
        )

    async def test_api_process_logs_traceback_and_continues(self):
        inbound_listener, (p1, p2, p3) = self._patches()
        with (
            p1,
            p2,
            p3,
            self.assertLogs(inbound_listener.logger, logging.ERROR) as logs,
        ):
            await inbound_listener.ensure_inbound_server()
        self.assertIsNotNone(logs.records[0].exc_info)

    async def test_dedicated_dispatcher_reraises(self):
        inbound_listener, (p1, p2, p3) = self._patches()
        with (
            p1,
            p2,
            p3,
            self.assertLogs(inbound_listener.logger, logging.ERROR),
            self.assertRaises(OSError),
        ):
            await inbound_listener.ensure_inbound_server(required=True)


if __name__ == "__main__":
    unittest.main()
