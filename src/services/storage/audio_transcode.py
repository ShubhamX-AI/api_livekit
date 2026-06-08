"""Transcode any user-uploaded audio into the canonical greeting format.

Uses PyAV (bundled ffmpeg, already a livekit-agents dependency) in-process — no
system ffmpeg binary and no subprocess. Accepts any format ffmpeg can decode
(mp3, m4a, ogg, wav, ...) and normalizes to WAV 48 kHz mono, the format the
worker plays back with.
"""

import io
import wave

import av
import numpy as np
from av.audio.resampler import AudioResampler

TARGET_SAMPLE_RATE = 48000
TARGET_CHANNELS = 1
MAX_SECONDS = 30.0
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB guard against oversized/compressed-bomb uploads


class AudioTooLong(Exception):
    """Raised when the audio exceeds MAX_SECONDS."""


class AudioDecodeError(Exception):
    """Raised when the upload can't be decoded as audio."""


def transcode_to_wav(data: bytes) -> tuple[bytes, float]:
    """Decode any audio to WAV 48kHz mono. Returns (wav_bytes, duration_seconds).

    Raises AudioTooLong if longer than MAX_SECONDS, AudioDecodeError otherwise.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        raise AudioDecodeError("File is too large")

    try:
        container = av.open(io.BytesIO(data))
    except Exception as e:
        raise AudioDecodeError(f"Unreadable audio file: {e}")

    try:
        if not container.streams.audio:
            raise AudioDecodeError("File has no audio stream")

        # Early reject using container metadata when available (avoids decoding huge files).
        if container.duration and container.duration / av.time_base > MAX_SECONDS:
            raise AudioTooLong("Audio is longer than 30 seconds")

        stream = container.streams.audio[0]
        resampler = AudioResampler(format="s16", layout="mono", rate=TARGET_SAMPLE_RATE)

        chunks = []
        for frame in container.decode(stream):
            for resampled in resampler.resample(frame):
                chunks.append(resampled.to_ndarray())
        for resampled in resampler.resample(None):  # flush
            chunks.append(resampled.to_ndarray())
    except (AudioTooLong, AudioDecodeError):
        raise
    except Exception as e:
        raise AudioDecodeError(f"Failed to decode audio: {e}")
    finally:
        container.close()

    if not chunks:
        raise AudioDecodeError("No audio samples decoded")

    pcm = np.concatenate(chunks, axis=1)  # shape (1, N) for mono
    duration = pcm.shape[1] / TARGET_SAMPLE_RATE
    if duration > MAX_SECONDS:  # fallback check when metadata duration was missing
        raise AudioTooLong("Audio is longer than 30 seconds")

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(TARGET_CHANNELS)
        wav.setsampwidth(2)  # s16
        wav.setframerate(TARGET_SAMPLE_RATE)
        wav.writeframes(pcm.astype(np.int16).tobytes())
    return buffer.getvalue(), duration
