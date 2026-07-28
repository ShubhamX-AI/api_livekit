"""Local speech gate for the agent's input audio track.

Background noise was interrupting the agent mid-sentence, and none of the LiveKit-side
interruption knobs could stop it in this deployment:

- Self-hosted LiveKit has no Cloud BVC/Krisp, and `agent_activity.py` skips adaptive
  interruption entirely when the worker is not Cloud-hosted.
- With `turn_detection="realtime_llm"` the SDK short-circuits VAD-based interruption, so
  `interruption["min_duration"]` / `min_words` never run, and `_on_input_speech_started`
  calls `interrupt()` unconditionally the moment the realtime model's own VAD flags
  speech-start.

That leaves the realtime model's VAD as the sole barge-in decision-maker, with nothing in
front of it. `AudioInputOptions.noise_cancellation` accepts any `rtc.FrameProcessor`
alongside the Cloud-only `NoiseCancellationOptions`, and a FrameProcessor runs in-process
in `rtc.AudioStream` — upstream of the realtime session and untouched by either constraint.
So the gate goes here: the model only ever hears what we let through.

Two stages:

1. WebRTC noise suppression + high-pass (`rtc.AudioProcessingModule`) — around -11 dB on
   stationary noise.
2. Silero VAD v5 (ONNX, CPU) — non-speech audio is zeroed, so noise cannot register as
   speech-start no matter how sensitive the model's VAD is.

AGC and AEC are deliberately off. AGC re-amplified the agent's own echo into false
barge-ins the last time it was enabled (see docs/architecture/audio-pipeline.md), and AEC
needs a reverse stream that RoomIO never feeds a FrameProcessor.
"""

from __future__ import annotations

import os

import numpy as np
import onnxruntime as ort
from livekit import rtc

from src.core.logger import logger

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "silero_vad.onnx")

# Calibration knobs. Real callers and real noise floors don't match any paper default —
# expect to tune these against live call recordings. Measured on 33 s of telephone-band
# speech and 56 s of office ambience (assets/audio/office-ambience_48k.wav):
#
#   thr / hangover   speech energy kept   ambience frames passed
#   0.35 / 800 ms          95.5%                  34.5%
#   0.50 / 600 ms          94.6%                  18.0%
#   0.70 / 500 ms          95.1%                  14.4%
#
# 0.50 is the knee: it costs nothing in speech versus 0.35 and cuts noise passthrough by
# a third. Going to 0.70 buys more but starts eating quiet speech.
_THRESHOLD = 0.5
"""Speech probability above which the gate opens. Lower to pass more audio if quiet callers
get clipped; raise if noise still reaches the model."""

_HANGOVER_MS = 600.0
"""How long the gate stays open after speech stops, so natural intra-sentence pauses don't
slam it shut. Directly multiplies the cost of a false positive — one bad window holds the
gate open this long — so it trades noise rejection against choppiness."""

_ATTENUATION = 0.0
"""Gain applied to non-speech audio. 0.0 is a hard gate; raise to ~0.1 if callers report
the line sounding dead between sentences."""

# Silero runs at its own rate on a resampled copy, so the audio the LLM receives keeps
# whatever rate RoomIO delivers. Each inference must be fed (context + window) samples,
# where the context is the tail of the previous window — feeding a bare window returns
# ~0.0 for everything, silently, because the ONNX graph declares a dynamic input shape and
# will not complain.
_VAD_RATE = 16000
_VAD_WINDOW = 512
_VAD_CONTEXT = 64


class SpeechGate(rtc.FrameProcessor[rtc.AudioFrame]):
    """Suppresses noise and mutes non-speech audio before it reaches the LLM.

    Stateful — the APM and the VAD both carry state across frames, so use one instance per
    audio stream, never share.
    """

    def __init__(self) -> None:
        self._enabled = True
        self._apm = rtc.AudioProcessingModule(noise_suppression=True, high_pass_filter=True)

        # One core per stream, not all of them: a worker runs many sessions concurrently
        # and ORT grabs every core by default.
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self._vad = ort.InferenceSession(
            _MODEL_PATH, sess_options=opts, providers=["CPUExecutionProvider"]
        )

        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._carry = np.empty(0, dtype=np.int16)
        self._context = np.zeros(_VAD_CONTEXT, dtype=np.float32)
        self._resampler: rtc.AudioResampler | None = None
        self._input_rate = 0
        self._hangover_ms = 0.0
        self._warned_format = False
        self._muted = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def muted(self) -> bool:
        return self._muted

    @muted.setter
    def muted(self, value: bool) -> None:
        """Force every frame to silence regardless of what the VAD thinks.

        Used by InputGuardController to blank the caller for the first seconds of an agent
        utterance. Muting here rather than calling `session.input.set_audio_enabled(False)`
        matters: detaching the input drops frames outright, and a realtime model that
        expects a continuous audio feed (notably Gemini Live) can misbehave on the gap.
        Silence keeps the stream flowing at the same rate.
        """
        self._muted = value

    def _speech_prob(self, chunk: np.ndarray) -> float:
        """Speech probability for one VAD window of int16 samples."""
        window = chunk.astype(np.float32) / 32768.0
        pcm = np.concatenate((self._context, window))[np.newaxis, :]
        out, self._state = self._vad.run(
            None,
            {"input": pcm, "state": self._state, "sr": np.array(_VAD_RATE, dtype=np.int64)},
        )
        self._context = window[-_VAD_CONTEXT:]
        return float(out[0][0])

    def _vad_samples(self, frame: rtc.AudioFrame) -> np.ndarray:
        """The frame's audio at Silero's rate. Only a copy is resampled — the frame the LLM
        receives keeps its original rate, so nothing above 8 kHz is lost on web calls."""
        if frame.sample_rate == _VAD_RATE:
            return np.asarray(frame.data)

        if self._resampler is None or self._input_rate != frame.sample_rate:
            self._input_rate = frame.sample_rate
            self._resampler = rtc.AudioResampler(
                input_rate=frame.sample_rate, output_rate=_VAD_RATE, num_channels=1
            )
        chunks = [np.asarray(f.data) for f in self._resampler.push(frame)]
        return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int16)

    def _process(self, frame: rtc.AudioFrame) -> rtc.AudioFrame:
        # APM rewrites the buffer in place and converts it to a bytearray, which is what
        # makes the samples writable below.
        self._apm.process_stream(frame)

        if frame.num_channels != 1:
            # The VAD is mono-only. Multi-channel audio still gets noise suppression.
            if not self._warned_format:
                self._warned_format = True
                logger.warning(
                    f"SpeechGate: VAD skipped, expected mono | channels={frame.num_channels}"
                )
            return frame

        samples = np.asarray(frame.data)

        # ponytail: gate opens if ANY window in this frame is speech, so a speech onset
        # mid-frame retroactively un-mutes the whole frame instead of clipping its start.
        # Ceiling: no cross-frame lookahead, so up to one frame of a phoneme can still be
        # attenuated if speech begins in the trailing sub-window bytes. If callers report
        # clipped first words, return a 3-frame-delayed frame (~150 ms constant latency)
        # rather than dropping _THRESHOLD into the noise floor.
        self._carry = np.concatenate((self._carry, self._vad_samples(frame)))
        speech = False
        while len(self._carry) >= _VAD_WINDOW:
            if self._speech_prob(self._carry[:_VAD_WINDOW]) >= _THRESHOLD:
                speech = True
            self._carry = self._carry[_VAD_WINDOW:]

        frame_ms = frame.samples_per_channel / frame.sample_rate * 1000.0
        if speech:
            self._hangover_ms = _HANGOVER_MS
        else:
            self._hangover_ms = max(0.0, self._hangover_ms - frame_ms)

        # The guard outranks the gate, and it blanks hard — _ATTENUATION is a gate knob, not
        # a guard one. Applied after the VAD ran on real audio so hangover state stays
        # honest across the muted stretch.
        if self._muted:
            samples[:] = 0
        elif not speech and self._hangover_ms <= 0.0:
            if _ATTENUATION == 0.0:
                samples[:] = 0
            else:
                samples[:] = (samples * _ATTENUATION).astype(np.int16)
        return frame

    def _close(self) -> None:
        self._vad = None
