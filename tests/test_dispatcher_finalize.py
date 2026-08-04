import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.services.outbound_dispatcher.dispatcher import (
    FINALIZE_WAIT_SECONDS,
    _finalize_if_agent_failed,
)


class RoomNameField:
    """Beanie field stand-in: `Model.room_name == value` must return something truthy."""

    def __eq__(self, other):
        return other


class TestFinalizeIfAgentFailed(unittest.IsolatedAsyncioTestCase):
    """The agent (session.py) owns the end-call webhook. The dispatcher must not race it.

    A caller-side hangup kills the SIP bridge ~6s before session.py finishes teardown.
    The old safety net wrote call_status="completed" at that moment, which made
    end_call() take its terminal-status shortcut and drop the webhook entirely.
    """

    async def test_waits_out_agent_teardown_then_does_nothing(self):
        # Record is still 'answered' for the first few polls, then session.py finalizes it.
        statuses = iter(["answered", "answered", "completed"])
        record = SimpleNamespace(call_status="answered")

        async def find_one(_query):
            record.call_status = next(statuses, "completed")
            return record

        with (
            patch("src.services.outbound_dispatcher.dispatcher.CallRecord") as model,
            patch("src.services.outbound_dispatcher.dispatcher.livekit_services") as svc,
            patch("src.services.outbound_dispatcher.dispatcher.asyncio.sleep", AsyncMock()),
        ):
            model.room_name = RoomNameField()
            model.find_one = find_one
            svc.end_call = AsyncMock()

            await _finalize_if_agent_failed("room-1", "assistant-1")

            # Agent got there — dispatcher must keep its hands off, or the webhook
            # would be sent twice and the duration overwritten.
            svc.end_call.assert_not_awaited()

    async def test_finalizes_when_agent_never_does(self):
        record = SimpleNamespace(call_status="answered")

        with (
            patch("src.services.outbound_dispatcher.dispatcher.CallRecord") as model,
            patch("src.services.outbound_dispatcher.dispatcher.livekit_services") as svc,
            patch(
                "src.services.outbound_dispatcher.dispatcher.asyncio.sleep", AsyncMock()
            ) as sleep,
        ):
            model.room_name = RoomNameField()
            model.find_one = AsyncMock(return_value=record)
            svc.end_call = AsyncMock()

            await _finalize_if_agent_failed("room-1", "assistant-1")

            # end_call() and not update_call_status(): it is what sends the webhook.
            svc.end_call.assert_awaited_once_with(
                room_name="room-1", assistant_id="assistant-1"
            )
            self.assertEqual(sleep.await_count, FINALIZE_WAIT_SECONDS)

    async def test_missing_record_still_finalizes(self):
        with (
            patch("src.services.outbound_dispatcher.dispatcher.CallRecord") as model,
            patch("src.services.outbound_dispatcher.dispatcher.livekit_services") as svc,
            patch("src.services.outbound_dispatcher.dispatcher.asyncio.sleep", AsyncMock()),
        ):
            model.room_name = RoomNameField()
            model.find_one = AsyncMock(return_value=None)
            svc.end_call = AsyncMock()

            await _finalize_if_agent_failed("room-1", None)

            svc.end_call.assert_awaited_once()

    async def test_end_call_failure_is_swallowed(self):
        # The monitor's finally block must still release the port and call_id.
        record = SimpleNamespace(call_status="answered")

        with (
            patch("src.services.outbound_dispatcher.dispatcher.CallRecord") as model,
            patch("src.services.outbound_dispatcher.dispatcher.livekit_services") as svc,
            patch("src.services.outbound_dispatcher.dispatcher.asyncio.sleep", AsyncMock()),
        ):
            model.room_name = RoomNameField()
            model.find_one = AsyncMock(return_value=record)
            svc.end_call = AsyncMock(side_effect=RuntimeError("mongo down"))

            await _finalize_if_agent_failed("room-1", "assistant-1")


if __name__ == "__main__":
    unittest.main()
