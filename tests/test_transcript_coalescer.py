import asyncio
import unittest
from datetime import datetime, timezone

from src.core.agents.stt.sarvam_parallel import FinalCoalescer


class TestFinalCoalescer(unittest.IsolatedAsyncioTestCase):
    """Sarvam endpoints on any pause longer than SpeechGate's 600 ms hangover, so one
    sentence arrives as several finals. The coalescer rejoins them into one transcript row.
    """

    def setUp(self) -> None:
        self.emitted: list[tuple[str, object]] = []

    def _make(self, window: float = 0.05) -> FinalCoalescer:
        return FinalCoalescer(lambda text, ts: self.emitted.append((text, ts)), window=window)

    async def test_fragments_inside_window_join_into_one_utterance(self):
        c = self._make()
        c.add("I want to")
        await asyncio.sleep(0.02)
        c.add("book a ticket")

        await asyncio.sleep(0.15)
        self.assertEqual([t for t, _ in self.emitted], ["I want to book a ticket"])

    async def test_timestamp_is_first_fragment_not_emission(self):
        c = self._make(window=0.2)
        before_first = datetime.now(timezone.utc)
        c.add("I want to")
        await asyncio.sleep(0.1)
        after_second = datetime.now(timezone.utc)
        c.add("book a ticket")

        await asyncio.sleep(0.4)
        (_, ts), = self.emitted
        # Stamped when the caller started talking, not when the merged row was emitted —
        # that is what keeps the utterance above the agent reply it triggered.
        self.assertGreaterEqual(ts, before_first)
        self.assertLess(ts, after_second)

    async def test_gap_longer_than_window_splits_utterances(self):
        c = self._make()
        c.add("first")
        await asyncio.sleep(0.15)
        c.add("second")
        await asyncio.sleep(0.15)

        self.assertEqual([t for t, _ in self.emitted], ["first", "second"])

    async def test_flush_emits_immediately_without_waiting_out_window(self):
        c = self._make(window=10.0)
        c.add("last thing I said")

        c.flush()
        self.assertEqual([t for t, _ in self.emitted], ["last thing I said"])

    async def test_flush_on_empty_buffer_is_a_noop(self):
        c = self._make()
        c.flush()
        c.flush()
        self.assertEqual(self.emitted, [])

    async def test_blank_fragments_are_ignored(self):
        c = self._make()
        c.add("   ")
        c.add("")
        c.flush()
        self.assertEqual(self.emitted, [])

    async def test_emit_failure_does_not_break_the_next_utterance(self):
        def boom(text, ts):
            raise RuntimeError("db down")

        c = FinalCoalescer(boom, window=0.05)
        c.add("dropped")
        c.flush()  # must not raise — a failed write cannot kill the STT tap

        self.emitted.clear()
        c._emit = lambda text, ts: self.emitted.append((text, ts))
        c.add("kept")
        c.flush()
        self.assertEqual([t for t, _ in self.emitted], ["kept"])


if __name__ == "__main__":
    unittest.main()
