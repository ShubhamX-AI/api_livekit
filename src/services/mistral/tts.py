from __future__ import annotations

import asyncio
import base64
import dataclasses
from dataclasses import dataclass

import aiohttp

from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS


API_BASE_URL = "https://api.mistral.ai/v1/audio/speech"
_SAMPLE_RATE = 22050  # MP3 default sample rate


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
        response_format: str = "mp3",
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=_SAMPLE_RATE,
            num_channels=1,
        )
        self._opts = _TTSOptions(
            api_key=api_key,
            voice_id=voice_id,
            model=model,
            response_format=response_format,
        )
        self._session = http_session

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "Mistral"

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return _MistralChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    async def aclose(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


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
        try:
            async with self._tts._ensure_session().post(
                API_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._opts.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._opts.model,
                    "input": self._input_text,
                    "voice_id": self._opts.voice_id,
                    "response_format": self._opts.response_format,
                },
                timeout=aiohttp.ClientTimeout(
                    total=30,
                    sock_connect=self._conn_options.timeout,
                ),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                audio_bytes = base64.b64decode(data["audio_data"])

                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=self._tts.sample_rate,
                    num_channels=self._tts.num_channels,
                    mime_type="audio/mp3",
                )
                output_emitter.push(audio_bytes)
                output_emitter.flush()

        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message,
                status_code=e.status,
                request_id=None,
                body=None,
            ) from e
        except Exception as e:
            raise APIConnectionError() from e
