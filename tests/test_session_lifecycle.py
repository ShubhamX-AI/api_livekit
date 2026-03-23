import unittest
import asyncio

from src.core.agents.session_lifecycle import CallReadinessGate


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


if __name__ == "__main__":
    unittest.main()
