import unittest
import wave

import numpy as np
from livekit import rtc
from scipy.signal import resample_poly

from src.core.agents.audio_denoise import SpeechGate

SAMPLE_RATE = 16000
FRAME = 800  # 50 ms, matching RoomIO's default frame_size_ms


def _load_16k(path: str) -> np.ndarray:
    with wave.open(path) as w:
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if channels > 1:
        pcm = pcm.reshape(-1, channels)[:, 0]
    if rate == SAMPLE_RATE:
        return pcm.copy()
    return resample_poly(pcm.astype(np.float32), SAMPLE_RATE, rate).astype(np.int16)


def _run(gate: SpeechGate, pcm: np.ndarray, passes: int = 1) -> tuple[np.ndarray, np.ndarray]:
    """Push pcm through the gate frame by frame; return per-frame input/output RMS.

    `passes=2` reproduces how RoomIO wires the gate in — the SDK applies the same instance
    both as the input stream's processor and as the AudioStream's noise_cancellation.
    """
    rms_in, rms_out = [], []
    for start in range(0, len(pcm) - FRAME, FRAME):
        chunk = pcm[start : start + FRAME].copy()
        frame = rtc.AudioFrame(
            data=chunk.tobytes(),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            samples_per_channel=FRAME,
        )
        rms_in.append(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))
        for _ in range(passes):
            gate._process(frame)
        out = np.asarray(frame.data).astype(np.float64)
        rms_out.append(np.sqrt(np.mean(out**2)))
    return np.array(rms_in), np.array(rms_out)


class TestSpeechGate(unittest.TestCase):
    """The gate is what stops background noise from interrupting the agent.

    Both directions matter: if it stops muting noise the barge-in bug returns, and if it
    starts muting speech the caller goes inaudible. A silent regression is likely here —
    Silero's ONNX input shape is dynamic, so feeding it the wrong window returns ~0.0 for
    every input without raising.
    """

    def test_steady_noise_is_muted(self):
        noise = (np.random.default_rng(0).normal(0, 1500, SAMPLE_RATE * 3)).astype(np.int16)
        rms_in, rms_out = _run(SpeechGate(), noise)

        self.assertGreater(rms_in.mean(), 1000, "test signal should be loud")
        self.assertLess(rms_out.max(), 1.0, "no noise frame should survive the gate")

    def test_real_ambience_is_mostly_muted(self):
        rms_in, rms_out = _run(SpeechGate(), _load_16k("assets/audio/office-ambience_48k.wav"))

        passed = rms_out.sum() / rms_in.sum()
        # This fixture has audible background voices, so some of it legitimately reads as
        # speech. Two thirds rejected is the win; demanding zero would be overfitting.
        self.assertLess(passed, 0.5, f"ambience mostly rejected, passed {passed:.0%}")

    def test_typing_noise_is_muted(self):
        _, rms_out = _run(SpeechGate(), _load_16k("assets/audio/typing-sound_48k.wav"))

        self.assertLess(rms_out.max(), 1.0, "keyboard clatter should never open the gate")

    def test_speech_passes_through(self):
        """Guards the failure mode that matters most: muting the actual caller.

        Uses the _speech_prob seam rather than a speech fixture — Silero rejects synthetic
        tones, and a real recording is not worth committing for one assertion.

        Asserts the gate does not mute, not that levels are untouched: stage 1 is a noise
        suppressor, and it attenuates a steady tone by design.
        """
        gate = SpeechGate()
        gate._speech_prob = lambda _chunk: 0.9

        tone = (np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 8000).astype(
            np.int16
        )
        rms_in, rms_out = _run(gate, tone)

        self.assertTrue((rms_out > 1.0).all(), "no frame should be muted while speech is on")
        self.assertGreater(rms_out.sum() / rms_in.sum(), 0.2)

    def test_hangover_holds_gate_open_after_speech_stops(self):
        gate = SpeechGate()
        probs = iter([0.9] + [0.0] * 100)
        gate._speech_prob = lambda _chunk: next(probs, 0.0)

        tone = (np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 8000).astype(
            np.int16
        )
        _, rms_out = _run(gate, tone)

        # 600 ms of hangover at 50 ms per frame: the speech frame plus ~12 more.
        open_frames = int(np.sum(rms_out > 1.0))
        self.assertGreater(open_frames, 8)
        self.assertLess(open_frames, 16)

    def test_hangover_is_unaffected_by_the_sdks_double_application(self):
        """RoomIO hands the same gate to the SDK twice, so every frame arrives twice.

        Without a guard the second pass scores the already-zeroed samples as silence and
        decrements the hangover again, halving it — which endpoints the model mid-sentence.
        """
        def open_frames(passes: int) -> int:
            gate = SpeechGate()
            probs = iter([0.9] + [0.0] * 100)
            gate._speech_prob = lambda _chunk: next(probs, 0.0)
            tone = (
                np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 8000
            ).astype(np.int16)
            _, rms_out = _run(gate, tone, passes=passes)
            return int(np.sum(rms_out > 1.0))

        self.assertEqual(open_frames(2), open_frames(1))

    def test_frame_geometry_is_preserved(self):
        gate = SpeechGate()
        chunk = (np.random.default_rng(1).normal(0, 1500, FRAME)).astype(np.int16)
        frame = rtc.AudioFrame(
            data=chunk.tobytes(),
            sample_rate=SAMPLE_RATE,
            num_channels=1,
            samples_per_channel=FRAME,
        )

        out = gate._process(frame)

        self.assertEqual(out.samples_per_channel, FRAME)
        self.assertEqual(out.sample_rate, SAMPLE_RATE)
        self.assertEqual(out.num_channels, 1)
        self.assertEqual(len(np.asarray(out.data)), FRAME)

    def test_gates_at_the_sdk_default_rate(self):
        """RoomIO delivers 24 kHz by default. The gate must resample its VAD copy and still
        mute noise, without changing the rate of the audio the model receives."""
        gate = SpeechGate()
        noise = (np.random.default_rng(2).normal(0, 1500, 24000 * 3)).astype(np.int16)
        frame_len = 1200  # 50 ms at 24 kHz
        rms_out = []
        for start in range(0, len(noise) - frame_len, frame_len):
            frame = rtc.AudioFrame(
                data=noise[start : start + frame_len].tobytes(),
                sample_rate=24000,
                num_channels=1,
                samples_per_channel=frame_len,
            )
            out = gate._process(frame)

            self.assertEqual(out.sample_rate, 24000, "frame rate must be left alone")
            self.assertEqual(out.samples_per_channel, frame_len)
            rms_out.append(np.sqrt(np.mean(np.asarray(out.data).astype(np.float64) ** 2)))

        self.assertLess(max(rms_out), 1.0, "noise must still be muted at 24 kHz")

    def test_muted_blanks_audio_even_during_speech(self):
        """InputGuardController's mechanism: the guard outranks the VAD's decision."""
        gate = SpeechGate()
        gate._speech_prob = lambda _chunk: 0.9
        gate.muted = True

        tone = (np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 8000).astype(
            np.int16
        )
        _, rms_out = _run(gate, tone)

        self.assertLess(max(rms_out), 1.0, "muted audio must be silent even when VAD says speech")

    def test_unmuting_restores_audio(self):
        gate = SpeechGate()
        gate._speech_prob = lambda _chunk: 0.9
        tone = (np.sin(2 * np.pi * 220 * np.arange(SAMPLE_RATE) / SAMPLE_RATE) * 8000).astype(
            np.int16
        )

        gate.muted = True
        _run(gate, tone)
        gate.muted = False
        _, rms_out = _run(gate, tone)

        self.assertTrue((rms_out > 1.0).all(), "audio must come back after the guard releases")

    def test_frames_keep_flowing_while_muted(self):
        """Why muting is used instead of session.input.set_audio_enabled(False): detaching
        drops frames, and a realtime model expecting a continuous feed can choke on the gap.
        """
        gate = SpeechGate()
        gate.muted = True
        noise = (np.random.default_rng(3).normal(0, 1500, SAMPLE_RATE)).astype(np.int16)

        rms_in, rms_out = _run(gate, noise)

        self.assertEqual(len(rms_out), len(rms_in), "no frame may be dropped while muted")

    def test_multichannel_audio_is_not_muted(self):
        """The VAD is mono-only; stereo must pass rather than be silenced."""
        gate = SpeechGate()
        chunk = (np.sin(2 * np.pi * 220 * np.arange(2400) / 24000) * 8000).astype(np.int16)
        frame = rtc.AudioFrame(
            data=chunk.tobytes(),
            sample_rate=24000,
            num_channels=2,
            samples_per_channel=1200,
        )

        gate._process(frame)

        out_rms = np.sqrt(np.mean(np.asarray(frame.data).astype(np.float64) ** 2))
        self.assertGreater(out_rms, 1000)


if __name__ == "__main__":
    unittest.main()
