import io
import unittest
import wave
from unittest.mock import MagicMock, patch

from src.services.storage import s3_audio
from src.services.storage.audio_transcode import (
    AudioDecodeError,
    AudioTooLong,
    transcode_to_wav,
)


def make_wav(sample_rate: int, channels: int, seconds: float = 1.0) -> bytes:
    """Build a silent WAV in memory for tests (any rate/channels — input to the transcoder)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * channels * int(sample_rate * seconds))
    return buffer.getvalue()


def wav_params(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as wav:
        return wav.getframerate(), wav.getnchannels()


class TestAudioTranscode(unittest.TestCase):
    def test_converts_8k_stereo_to_48k_mono(self):
        wav_bytes, duration = transcode_to_wav(make_wav(8000, 2, seconds=3))
        self.assertAlmostEqual(duration, 3.0, places=1)
        self.assertEqual(wav_params(wav_bytes), (48000, 1))

    def test_passthrough_48k_mono(self):
        wav_bytes, duration = transcode_to_wav(make_wav(48000, 1, seconds=5))
        self.assertAlmostEqual(duration, 5.0, places=1)
        self.assertEqual(wav_params(wav_bytes), (48000, 1))

    def test_rejects_longer_than_30s(self):
        with self.assertRaises(AudioTooLong):
            transcode_to_wav(make_wav(48000, 1, seconds=31))

    def test_accepts_exactly_30s(self):
        _, duration = transcode_to_wav(make_wav(48000, 1, seconds=30))
        self.assertAlmostEqual(duration, 30.0, places=1)

    def test_rejects_non_audio_bytes(self):
        with self.assertRaises(AudioDecodeError):
            transcode_to_wav(b"not an audio file")


class TestS3AudioHelper(unittest.TestCase):
    def test_build_key_uses_audio_id(self):
        self.assertTrue(s3_audio.build_key("aud-123").endswith("aud-123.wav"))

    @patch("src.services.storage.s3_audio._client")
    def test_upload_puts_object_and_returns_key(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        key = s3_audio.upload("aud-123", b"audio-bytes")

        self.assertEqual(key, s3_audio.build_key("aud-123"))
        kwargs = client.put_object.call_args.kwargs
        self.assertEqual(kwargs["Key"], key)
        self.assertEqual(kwargs["Body"], b"audio-bytes")
        self.assertEqual(kwargs["ContentType"], "audio/wav")

    @patch("src.services.storage.s3_audio._client")
    def test_download_writes_tempfile(self, mock_client):
        client = MagicMock()
        client.get_object.return_value = {"Body": io.BytesIO(b"wav-bytes")}
        mock_client.return_value = client

        path = s3_audio.download_to_tempfile("some/key.wav")

        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"wav-bytes")

    @patch("src.services.storage.s3_audio._client")
    def test_delete_calls_delete_object(self, mock_client):
        client = MagicMock()
        mock_client.return_value = client

        s3_audio.delete("some/key.wav")

        self.assertEqual(client.delete_object.call_args.kwargs["Key"], "some/key.wav")

    def test_public_url_is_plain_and_unsigned(self):
        url = s3_audio.public_url("greeting_audio/aud-123.wav")
        self.assertTrue(url.startswith("https://"))
        self.assertIn(".amazonaws.com/greeting_audio/aud-123.wav", url)
        self.assertNotIn("?", url)  # no presign query string / no expiry


class FakeAsset:
    """Duck-types the bits serialize_asset reads (Beanie docs need a live DB to instantiate)."""

    def __init__(self, s3_url):
        self.s3_key = "greeting_audio/aud-1.wav"
        self.s3_url = s3_url

    def model_dump(self, exclude=None):
        data = {
            "audio_id": "aud-1",
            "audio_name": "Welcome",
            "s3_key": self.s3_key,
            "s3_url": self.s3_url,
        }
        for field in exclude or set():
            data.pop(field, None)
        return data


class TestSerializeAsset(unittest.TestCase):
    def test_hides_s3_key_and_returns_stored_url(self):
        from src.api.routes.audio import serialize_asset

        data = serialize_asset(FakeAsset("https://bucket.s3.region.amazonaws.com/greeting_audio/aud-1.wav"))
        self.assertNotIn("s3_key", data)
        self.assertEqual(data["s3_url"], "https://bucket.s3.region.amazonaws.com/greeting_audio/aud-1.wav")


if __name__ == "__main__":
    unittest.main()
