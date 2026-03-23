import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from src.services.livekit.livekit_svc import LiveKitService


class FakeCallRecord:
    def __init__(self, status="initiated", answered_at=None):
        self.room_name = "room-1"
        self.assistant_id = "assistant-1"
        self.assistant_name = "Assistant"
        self.to_number = "+911234567890"
        self.call_status = status
        self.call_status_reason = None
        self.sip_status_code = None
        self.sip_status_text = None
        self.answered_at = answered_at
        self.recording_path = None
        self.recording_egress_id = "EG_test_123"
        self.transcripts = []
        self.started_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.ended_at = None
        self.call_duration_minutes = None

    async def save(self):
        return None


class RoomNameField:
    def __eq__(self, other):
        return other


class TestLiveKitLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_end_call_prefers_answered_at_for_duration(self):
        svc = LiveKitService()
        answered_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        record = FakeCallRecord(status="answered", answered_at=answered_at)

        with patch("src.services.livekit.livekit_svc.CallRecord") as call_record_model:
            call_record_model.room_name = RoomNameField()
            call_record_model.find_one = AsyncMock(return_value=record)
            svc.stop_room_recording = AsyncMock(return_value=True)
            svc.send_end_call_webhook = AsyncMock(return_value=True)

            await svc.end_call(room_name="room-1", assistant_id="assistant-1")

            self.assertEqual(record.call_status, "completed")
            self.assertIsNotNone(record.ended_at)
            self.assertAlmostEqual(record.call_duration_minutes * 60, 30, delta=2)
            svc.stop_room_recording.assert_awaited_once_with("EG_test_123")
            self.assertEqual(svc.send_end_call_webhook.await_count, 1)

    async def test_end_call_falls_back_to_started_at_when_answered_missing(self):
        svc = LiveKitService()
        record = FakeCallRecord(status="initiated")

        with patch("src.services.livekit.livekit_svc.CallRecord") as call_record_model:
            call_record_model.room_name = RoomNameField()
            call_record_model.find_one = AsyncMock(return_value=record)
            svc.stop_room_recording = AsyncMock(return_value=True)
            svc.send_end_call_webhook = AsyncMock(return_value=True)
            await svc.end_call(room_name="room-1", assistant_id="assistant-1")

            self.assertAlmostEqual(record.call_duration_minutes * 60, 60, delta=2)
            self.assertEqual(svc.send_end_call_webhook.await_count, 1)

    async def test_end_call_skips_duplicate_completed_status(self):
        svc = LiveKitService()
        record = FakeCallRecord(status="completed")

        with patch("src.services.livekit.livekit_svc.CallRecord") as call_record_model:
            call_record_model.room_name = RoomNameField()
            call_record_model.find_one = AsyncMock(return_value=record)
            svc.stop_room_recording = AsyncMock(return_value=True)
            svc.send_end_call_webhook = AsyncMock(return_value=True)

            await svc.end_call(room_name="room-1", assistant_id="assistant-1")

            svc.stop_room_recording.assert_not_awaited()
            svc.send_end_call_webhook.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
