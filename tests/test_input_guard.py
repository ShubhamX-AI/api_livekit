import asyncio
import logging
import unittest

from src.core.agents.voice_features import InputGuardController


class FakeGate:
    """Stands in for SpeechGate — the guard only touches `.muted`."""

    def __init__(self) -> None:
        self.muted = False


class TestInputGuardController(unittest.IsolatedAsyncioTestCase):
    """The guard is what blocks filler sounds ("um", "uh") and repeated "Hello?" from
    interrupting the agent. SpeechGate cannot: those are genuine speech.
    """

    def setUp(self) -> None:
        self.gate = FakeGate()
        self.logger = logging.getLogger("test-input-guard")

    async def test_mutes_while_agent_speaks_and_restores_after_window(self):
        guard = InputGuardController(logger=self.logger, gate=self.gate, window_sec=0.05)

        guard.on_speaking_start()
        self.assertTrue(self.gate.muted)

        await asyncio.sleep(0.15)
        self.assertFalse(self.gate.muted, "window expired, caller must be audible again")

    async def test_restores_early_when_agent_stops_speaking(self):
        guard = InputGuardController(logger=self.logger, gate=self.gate, window_sec=10.0)

        guard.on_speaking_start()
        guard.on_speaking_end()

        self.assertFalse(self.gate.muted, "must not make the caller wait out a 10s window")

    async def test_repeated_speaking_start_is_idempotent(self):
        guard = InputGuardController(logger=self.logger, gate=self.gate, window_sec=0.05)

        guard.on_speaking_start()
        guard.on_speaking_start()
        await asyncio.sleep(0.15)

        self.assertFalse(self.gate.muted)

    async def test_aclose_never_leaves_the_caller_muted(self):
        """The worst outcome is a caller silenced for the rest of the call."""
        guard = InputGuardController(logger=self.logger, gate=self.gate, window_sec=10.0)

        guard.on_speaking_start()
        await guard.aclose()

        self.assertFalse(self.gate.muted)


if __name__ == "__main__":
    unittest.main()
