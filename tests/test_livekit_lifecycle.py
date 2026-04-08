import unittest
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.services.livekit.livekit_svc import LiveKitService
from src.core.billing import calculate_billable_duration_minutes


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
        self.billable_duration_minutes = None

    async def save(self):
        return None

    def model_dump_json(self):
        return json.dumps(
            {
                "id": "mongo-id",
                "room_name": self.room_name,
                "assistant_id": self.assistant_id,
                "assistant_name": self.assistant_name,
                "to_number": self.to_number,
                "call_status": self.call_status,
                "call_status_reason": self.call_status_reason,
                "sip_status_code": self.sip_status_code,
                "sip_status_text": self.sip_status_text,
                "answered_at": self.answered_at.isoformat() if self.answered_at else None,
                "recording_path": self.recording_path,
                "transcripts": self.transcripts,
                "started_at": self.started_at.isoformat(),
                "ended_at": self.ended_at.isoformat() if self.ended_at else None,
                "call_duration_minutes": self.call_duration_minutes,
                "billable_duration_minutes": self.billable_duration_minutes,
                "created_by_email": "user@example.com",
                "call_type": "outbound",
                "call_service": "exotel",
                "platform_number": "08044319240",
            }
        )


class RoomNameField:
    def __eq__(self, other):
        return other

    def __ne__(self, other):
        return other


class FakeActivityLog:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def insert(self):
        return None


class TestLiveKitLifecycle(unittest.IsolatedAsyncioTestCase):
    def test_calculate_billable_duration_minutes_rounds_up_connected_calls(self):
        self.assertEqual(calculate_billable_duration_minutes("completed", 0.30), 1)
        self.assertEqual(calculate_billable_duration_minutes("completed", 1.25), 2)
        self.assertEqual(calculate_billable_duration_minutes("completed", 2.0), 2)
        self.assertEqual(calculate_billable_duration_minutes("failed", 1.25), 0)

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
            self.assertEqual(record.billable_duration_minutes, 1)
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
            self.assertEqual(
                record.billable_duration_minutes,
                calculate_billable_duration_minutes("completed", record.call_duration_minutes),
            )
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

    async def test_update_call_status_sets_zero_billable_for_failed_call(self):
        svc = LiveKitService()
        record = FakeCallRecord(status="initiated")

        with patch("src.services.livekit.livekit_svc.CallRecord") as call_record_model:
            call_record_model.room_name = RoomNameField()
            call_record_model.find_one = AsyncMock(return_value=record)

            await svc.update_call_status(
                room_name="room-1",
                call_status="failed",
                ended_at=datetime.now(timezone.utc),
                call_duration_minutes=0,
            )

            self.assertEqual(record.call_status, "failed")
            self.assertEqual(record.billable_duration_minutes, 0)

    async def test_send_end_call_webhook_includes_billable_duration_minutes(self):
        svc = LiveKitService()
        record = FakeCallRecord(status="completed")
        record.call_duration_minutes = 1.25
        record.billable_duration_minutes = 2
        posted = {}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json):
                posted["url"] = url
                posted["payload"] = json
                return SimpleNamespace(status_code=200)

        assistant_model = SimpleNamespace(
            assistant_id=RoomNameField(),
            assistant_end_call_url=RoomNameField(),
            find_one=AsyncMock(
                return_value=SimpleNamespace(
                    assistant_end_call_url="https://example.com/webhook",
                    assistant_created_by_email="user@example.com",
                )
            ),
        )
        call_record_model = SimpleNamespace(
            room_name=RoomNameField(),
            find_one=AsyncMock(return_value=record),
        )
        usage_record_model = SimpleNamespace(
            room_name=RoomNameField(),
            find_one=AsyncMock(return_value=None),
        )

        with patch("src.services.livekit.livekit_svc.CallRecord", call_record_model), patch(
            "src.services.livekit.livekit_svc.Assistant", assistant_model
        ), patch("src.services.livekit.livekit_svc.UsageRecord", usage_record_model), patch(
            "src.services.livekit.livekit_svc.ActivityLog", FakeActivityLog
        ), patch("src.services.livekit.livekit_svc.httpx.AsyncClient", FakeAsyncClient):
            await svc.send_end_call_webhook(room_name="room-1", assistant_id="assistant-1")

        self.assertEqual(posted["url"], "https://example.com/webhook")
        self.assertEqual(posted["payload"]["data"]["call_duration_minutes"], 1.25)
        self.assertEqual(posted["payload"]["data"]["billable_duration_minutes"], 2)


if __name__ == "__main__":
    unittest.main()
