from __future__ import annotations

import asyncio
import dataclasses
import os
from dataclasses import dataclass
from typing import Literal

import aiohttp

from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIError,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given


TTSEncoding = Literal[
    "alaw_8000",
    "mp3_22050_32",
    "mp3_24000_48",
    "mp3_44100_128",
    "mp3_44100_192",
    "mp3_44100_32",
    "mp3_44100_64",
    "mp3_44100_96",
    "opus_48000_128",
    "opus_48000_192",
    "opus_48000_32",
    "opus_48000_64",
    "opus_48000_96",
    "pcm_16000",
    "pcm_22050",
    "pcm_24000",
    "pcm_32000",
    "pcm_44100",
    "pcm_48000",
    "pcm_8000",
    "ulaw_8000",
    "wav_16000",
    "wav_22050",
    "wav_24000",
    "wav_32000",
    "wav_44100",
    "wav_48000",
    "wav_8000",
]

API_BASE_URL_V1 = "https://api.elevenlabs.io/v1"
AUTHORIZATION_HEADER = "xi-api-key"
_DEFAULT_ENCODING: TTSEncoding = "mp3_22050_32"


def _sample_rate_from_format(output_format: TTSEncoding) -> int:
    split = output_format.split("_")
    return int(split[1])


def _encoding_to_mimetype(encoding: TTSEncoding) -> str:
    if encoding.startswith("mp3"):
        return "audio/mp3"
    if encoding.startswith("opus"):
        return "audio/opus"
    if encoding.startswith("pcm"):
        return "audio/pcm"
    if encoding.startswith("wav"):
        return "audio/wav"
    if encoding.startswith("alaw"):
        return "audio/alaw"
    if encoding.startswith("ulaw"):
        return "audio/ulaw"
    raise ValueError(f"Unsupported encoding: {encoding}")


@dataclass
class VoiceSettings:
    stability: float
    similarity_boost: float
    style: NotGivenOr[float] = NOT_GIVEN
    speed: NotGivenOr[float] = NOT_GIVEN
    use_speaker_boost: NotGivenOr[bool] = NOT_GIVEN


@dataclass
class _TTSOptions:
    api_key: str
    voice_id: str
    model: str
    encoding: TTSEncoding
    base_url: str
    voice_settings: NotGivenOr[VoiceSettings]
    enable_logging: bool
    apply_text_normalization: Literal["auto", "on", "off"]
    language: NotGivenOr[str]
    optimize_latency: NotGivenOr[int]


class ElevenLabsNonStreamingTTS(tts.TTS):
    def __init__(
        self,
        *,
        voice_id: str,
        model: str = "eleven_v3",
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        api_key: NotGivenOr[str] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        voice_settings: NotGivenOr[VoiceSettings] = NOT_GIVEN,
        enable_logging: bool = True,
        apply_text_normalization: Literal["auto", "on", "off"] = "auto",
        language: NotGivenOr[str] = NOT_GIVEN,
        optimize_latency: NotGivenOr[int] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        if not is_given(encoding):
            encoding = _DEFAULT_ENCODING

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False, aligned_transcript=False),
            sample_rate=_sample_rate_from_format(encoding),
            num_channels=1,
        )

        elevenlabs_api_key = api_key if is_given(api_key) else os.environ.get("ELEVEN_API_KEY")
        if not elevenlabs_api_key:
            raise ValueError(
                "ElevenLabs API key is required, either as argument or set ELEVEN_API_KEY environmental variable"
            )

        self._opts = _TTSOptions(
            api_key=elevenlabs_api_key,
            voice_id=voice_id,
            model=model,
            encoding=encoding,
            base_url=base_url if is_given(base_url) else API_BASE_URL_V1,
            voice_settings=voice_settings,
            enable_logging=enable_logging,
            apply_text_normalization=apply_text_normalization,
            language=language,
            optimize_latency=optimize_latency,
        )
        self._session = http_session

    @property
    def model(self) -> str:
        return self._opts.model

    @property
    def provider(self) -> str:
        return "ElevenLabs"

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return _ChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    async def aclose(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None


class _ChunkedStream(tts.ChunkedStream):
    def __init__(
        self,
        *,
        tts: ElevenLabsNonStreamingTTS,
        input_text: str,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts
        self._opts = dataclasses.replace(tts._opts)

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        voice_settings = (
            _strip_nones(dataclasses.asdict(self._opts.voice_settings))
            if is_given(self._opts.voice_settings)
            else None
        )
        try:
            async with self._tts._ensure_session().post(
                _synthesize_url(self._opts),
                headers={AUTHORIZATION_HEADER: self._opts.api_key},
                json={
                    "text": self._input_text,
                    "model_id": self._opts.model,
                    "voice_settings": voice_settings,
                    "apply_text_normalization": self._opts.apply_text_normalization,
                    "language_code": self._opts.language if is_given(self._opts.language) else None,
                },
                timeout=aiohttp.ClientTimeout(
                    total=30,
                    sock_connect=self._conn_options.timeout,
                ),
            ) as resp:
                resp.raise_for_status()

                if not (
                    resp.content_type.startswith("audio/")
                    or resp.content_type == "application/octet-stream"
                ):
                    content = await resp.text()
                    raise APIError(message="ElevenLabs returned non-audio data", body=content)

                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=self._tts.sample_rate,
                    num_channels=self._tts.num_channels,
                    mime_type=_encoding_to_mimetype(self._opts.encoding),
                )

                async for data, _ in resp.content.iter_chunks():
                    output_emitter.push(data)

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


def _synthesize_url(opts: _TTSOptions) -> str:
    url = (
        f"{opts.base_url}/text-to-speech/{opts.voice_id}?output_format={opts.encoding}"
        f"&enable_logging={str(opts.enable_logging).lower()}"
    )
    if is_given(opts.optimize_latency):
        url += f"&optimize_streaming_latency={opts.optimize_latency}"
    return url


def _strip_nones(data: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in data.items() if is_given(v) and v is not None}
