from __future__ import annotations

import asyncio
import base64
import dataclasses
from dataclasses import dataclass

from mistralai.client import Mistral

from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APITimeoutError,
    tts,
    utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS


_PCM_SAMPLE_RATE = 22050  # Mistral voxtral PCM output sample rate

# Map response_format → mime type for output_emitter
_MIME_TYPES = {
    "pcm": "audio/pcm",
    "mp3": "audio/mp3",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "flac": "audio/flac",
}


@dataclass
class _TTSOptions:
    api_key: str
    voice_id: str
    model: str
    response_format: str


class MistralTTS(tts.TTS):
    def __init__(
        self,
        *,
        voice_id: str,
        model: str = "voxtral-mini-tts-2603",
        api_key: str,
        response_format: str = "opus",
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=_PCM_SAMPLE_RATE,
            num_channels=1,
        )
        self._opts = _TTSOptions(
            api_key=api_key,
            voice_id=voice_id,
            model=model,
            response_format=response_format,
        )
        self._client = Mistral(api_key=api_key)

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "Mistral"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return _MistralChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    async def aclose(self) -> None:
        pass


class _MistralChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: MistralTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts
        self._opts = dataclasses.replace(tts._opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        mime_type = _MIME_TYPES.get(self._opts.response_format, "audio/pcm")

        def _sync_synthesize() -> list[bytes]:
            """Run the blocking Mistral SDK call in a thread."""
            chunks = []
            with self._tts._client.audio.speech.complete(
                input=self._input_text,
                model=self._opts.model,
                voice_id=self._opts.voice_id,
                response_format=self._opts.response_format,
                stream=True,
            ) as stream:
                for event in stream:
                    if event.event == "speech.audio.delta":
                        chunks.append(base64.b64decode(event.data.audio_data))
                    elif event.event == "speech.audio.done":
                        break
            return chunks

        try:
            loop = asyncio.get_running_loop()
            chunks = await asyncio.wait_for(
                loop.run_in_executor(None, _sync_synthesize),
                timeout=self._conn_options.timeout,
            )

            output_emitter.initialize(
                request_id=utils.shortuuid(),
                sample_rate=self._tts.sample_rate,
                num_channels=self._tts.num_channels,
                mime_type=mime_type,
            )

            for chunk in chunks:
                output_emitter.push(chunk)

            output_emitter.flush()

        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except Exception as e:
            raise APIConnectionError() from e
