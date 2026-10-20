import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from src.api.routes import audio
from src.services.storage.audio_transcode import MAX_UPLOAD_BYTES


class _FakeUpload:
    """Stands in for starlette's UploadFile; records every read() size it is asked for."""

    filename = "clip.wav"

    def __init__(self, size: int):
        self._size = size
        self.read_sizes: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        n = self._size if size < 0 else min(size, self._size)
        return b"\x00" * n


class TestUploadSizeLimit(unittest.TestCase):
    def _upload(self, file: _FakeUpload):
        return asyncio.run(
            audio.upload_audio(file=file, audio_name="x", transcript="x", current_user=None)
        )

    def test_read_is_bounded_to_one_byte_past_the_cap(self):
        file = _FakeUpload(size=MAX_UPLOAD_BYTES * 10)
        with self.assertRaises(HTTPException) as ctx:
            self._upload(file)
        self.assertEqual(file.read_sizes, [MAX_UPLOAD_BYTES + 1])
        self.assertEqual(ctx.exception.status_code, 400)

    def test_oversized_file_never_reaches_the_transcoder(self):
        file = _FakeUpload(size=MAX_UPLOAD_BYTES + 1)
        with patch.object(audio, "transcode_to_wav") as transcode, self.assertRaises(HTTPException):
            self._upload(file)
        transcode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
