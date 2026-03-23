import unittest
import asyncio
from unittest.mock import AsyncMock

from src.core.agents.session_lifecycle import CallReadinessGate, RecordingManager


class TestCallReadinessGate(unittest.IsolatedAsyncioTestCase):
    async def test_exotel_outbound_gate_is_closed_initially(self):
        gate = CallReadinessGate(is_exotel_outbound=True)
        self.assertFalse(gate.is_active)
        
    async def test_exotel_outbound_gate_opens_on_answered(self):
        gate = CallReadinessGate(is_exotel_outbound=True)
        gate.mark_answered()
        self.assertTrue(gate.is_active)

    async def test_non_exotel_gate_is_open_initially(self):
        gate = CallReadinessGate(is_exotel_outbound=False)
        self.assertTrue(gate.is_active)

    async def test_wait_until_ready_returns_false_on_timeout(self):
        gate = CallReadinessGate(is_exotel_outbound=True)
        # Timeout quickly for the test
        is_ready = await gate.wait_until_ready(timeout=0.1)
        self.assertFalse(is_ready)

    async def test_wait_until_ready_returns_true_if_already_open(self):
        gate = CallReadinessGate(is_exotel_outbound=False)
        is_ready = await gate.wait_until_ready(timeout=0.1)
        self.assertTrue(is_ready)

    async def test_wait_until_ready_returns_true_when_answered(self):
        gate = CallReadinessGate(is_exotel_outbound=True)
        
        async def mark_answered_later():
            await asyncio.sleep(0.05)
            gate.mark_answered()

        asyncio.create_task(mark_answered_later())
        is_ready = await gate.wait_until_ready(timeout=0.2)
        self.assertTrue(is_ready)


class TestRecordingManager(unittest.IsolatedAsyncioTestCase):
    async def test_ensure_started_waits_until_recording_ready(self):
        fake_lk = AsyncMock()
        fake_lk.start_room_recording = AsyncMock(
            return_value={
                "success": True,
                "data": {"s3_url": "https://s3/foo.ogg", "egress_id": "EG_123"},
            }
        )
        recorder = RecordingManager(fake_lk, room_name="room-1", assistant_id="assistant-1")

        ok = await recorder.ensure_started(timeout=1.0)

        self.assertTrue(ok)
        self.assertEqual(recorder.s3_url, "https://s3/foo.ogg")
        self.assertEqual(recorder.egress_id, "EG_123")
        self.assertEqual(fake_lk.start_room_recording.await_count, 1)

    async def test_ensure_started_returns_false_on_timeout(self):
        fake_lk = AsyncMock()

        async def slow_start(*args, **kwargs):
            await asyncio.sleep(0.2)
            return {"success": True, "data": {"s3_url": "late", "egress_id": "EG_late"}}

        fake_lk.start_room_recording = AsyncMock(side_effect=slow_start)
        recorder = RecordingManager(fake_lk, room_name="room-1", assistant_id="assistant-1")

        ok = await recorder.ensure_started(timeout=0.05)

        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
