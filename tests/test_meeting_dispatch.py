import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.api.routes import meeting_call
from src.services.livekit import livekit_svc
from src.services.livekit.livekit_svc import LiveKitService


class RoomNameField:
    def __eq__(self, value):
        return value


class TestNamedAgentDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_default_agent_name_is_preserved(self):
        requests = []

        class Dispatch:
            async def create_dispatch(self, request):
                requests.append(request)
                return SimpleNamespace()

        service = LiveKitService()

        @asynccontextmanager
        async def fake_client():
            yield SimpleNamespace(agent_dispatch=Dispatch())

        service.get_livekit_api = fake_client
        await service.create_agent_dispatch("room", {"call_type": "web"})

        self.assertEqual(requests[0].agent_name, "api-agent")

    async def test_named_agent_dispatch_forwards_metadata(self):
        requests = []

        class Dispatch:
            async def create_dispatch(self, request):
                requests.append(request)
                return SimpleNamespace()

        service = LiveKitService()

        @asynccontextmanager
        async def fake_client():
            yield SimpleNamespace(agent_dispatch=Dispatch())

        service.get_livekit_api = fake_client
        await service.create_agent_dispatch(
            "room",
            {"call_type": "meeting", "meeting_url": "https://meet.google.com/abc-defg-hij"},
            agent_name="meet-connector",
        )

        self.assertEqual(requests[0].agent_name, "meet-connector")
        self.assertIn("meeting_url", requests[0].metadata)


class TestMeetingConnectorEvents(unittest.IsolatedAsyncioTestCase):
    async def test_connector_ready_is_persisted_once(self):
        record = SimpleNamespace(
            call_type="meeting",
            meeting_connector_status=None,
            meeting_connector_status_reason=None,
            meeting_connector_ready_at=None,
            meeting_connector_ended_at=None,
            save=AsyncMock(),
        )
        model = SimpleNamespace(room_name=RoomNameField())
        model.find_one = AsyncMock(return_value=record)
        original = livekit_svc.CallRecord
        livekit_svc.CallRecord = model
        try:
            service = LiveKitService()
            await service.record_meeting_connector_event("room", "ready")
            ready_at = record.meeting_connector_ready_at
            await service.record_meeting_connector_event("room", "ready")
        finally:
            livekit_svc.CallRecord = original

        self.assertEqual(record.meeting_connector_status, "ready")
        self.assertIs(record.meeting_connector_ready_at, ready_at)
        self.assertEqual(record.save.await_count, 2)

    async def test_terminal_connector_event_cannot_be_reopened(self):
        record = SimpleNamespace(
            call_type="meeting",
            meeting_connector_status="failed",
            meeting_connector_status_reason="browser failed",
            meeting_connector_ready_at=None,
            meeting_connector_ended_at=None,
            save=AsyncMock(),
        )
        model = SimpleNamespace(room_name=RoomNameField())
        model.find_one = AsyncMock(return_value=record)
        original = livekit_svc.CallRecord
        livekit_svc.CallRecord = model
        try:
            service = LiveKitService()
            await service.record_meeting_connector_event("room", "ready")
        finally:
            livekit_svc.CallRecord = original

        self.assertEqual(record.meeting_connector_status, "failed")
        record.save.assert_not_awaited()


class TestAbandonedSetupReportsFailure(unittest.IsolatedAsyncioTestCase):
    """A meeting whose setup fails has to tell the caller, like every other call type.

    `end_call` resolves the end-call webhook URL from the assistant, so abandoning a room without
    an assistant id silently skips the webhook. That is invisible in logs and leaves an API client
    waiting for a call that will never happen.
    """

    async def _abandon(self, *, assistant_id):
        service = SimpleNamespace(
            update_call_status=AsyncMock(),
            end_call=AsyncMock(),
            delete_room=AsyncMock(),
        )
        original = meeting_call.livekit_services
        meeting_call.livekit_services = service
        try:
            await meeting_call._abandon_room("room", assistant_id)
        finally:
            meeting_call.livekit_services = original
        return service

    async def test_assistant_id_reaches_end_call(self):
        service = await self._abandon(assistant_id="assistant-1")

        service.end_call.assert_awaited_once_with("room", "assistant-1")
        service.delete_room.assert_awaited_once_with("room")

    async def test_room_is_still_cleaned_up_when_marking_failed_raises(self):
        service = SimpleNamespace(
            update_call_status=AsyncMock(side_effect=RuntimeError("mongo down")),
            end_call=AsyncMock(),
            delete_room=AsyncMock(),
        )
        original = meeting_call.livekit_services
        meeting_call.livekit_services = service
        try:
            await meeting_call._abandon_room("room", "assistant-1")
        finally:
            meeting_call.livekit_services = original

        service.end_call.assert_awaited_once()
        service.delete_room.assert_awaited_once()

    async def test_missing_room_name_is_a_no_op(self):
        service = SimpleNamespace(
            update_call_status=AsyncMock(),
            end_call=AsyncMock(),
            delete_room=AsyncMock(),
        )
        original = meeting_call.livekit_services
        meeting_call.livekit_services = service
        try:
            await meeting_call._abandon_room(None, "assistant-1")
        finally:
            meeting_call.livekit_services = original

        service.update_call_status.assert_not_awaited()
        service.end_call.assert_not_awaited()
        service.delete_room.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
