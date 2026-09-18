import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


if __name__ == "__main__":
    unittest.main()
