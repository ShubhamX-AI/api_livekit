"""Factory for creating TTS provider instances based on assistant configuration."""

from livekit.plugins import cartesia, sarvam

from src.core.config import settings
from src.core.logger import logger
from src.services.elevenlabs.v3_nonstream import ElevenLabsNonStreamingTTS
from src.services.mistral.tts import MistralTTS


def create_tts(assistant):
    """Build a TTS instance from the assistant's model + config. Returns None on error."""
    tts_config = assistant.assistant_tts_config or {}
    model = assistant.assistant_tts_model
    assistant_id = assistant.assistant_id

    if model == "cartesia":
        voice_id = tts_config.get("voice_id")
        if not voice_id:
            logger.error(f"Missing voice_id for Cartesia assistant {assistant_id}")
            return None
        api_key = tts_config.get("api_key") or settings.CARTESIA_API_KEY
        return cartesia.TTS(
            model="sonic-3",
            speed=1.1,
            voice=voice_id,
            api_key=api_key,
        )

    if model == "sarvam":
        speaker = tts_config.get("speaker")
        if not speaker:
            logger.error(f"Missing speaker for Sarvam assistant {assistant_id}")
            return None
        api_key = tts_config.get("api_key") or settings.SARVAM_API_KEY
        return sarvam.TTS(
            model="bulbul:v3",
            pace=1.1,
            speech_sample_rate=24000,
            target_language_code=tts_config.get("target_language_code", "en-IN"),
            speaker=speaker,
            api_key=api_key,
        )

    if model == "elevenlabs":
        voice_id = tts_config.get("voice_id")
        if not voice_id:
            logger.error(f"Missing voice_id for ElevenLabs assistant {assistant_id}")
            return None
        api_key = tts_config.get("api_key") or settings.ELEVENLABS_API_KEY
        return ElevenLabsNonStreamingTTS(
            model="eleven_v3",
            voice_id=voice_id,
            api_key=api_key,
        )

    if model == "mistral":
        voice_id = tts_config.get("voice_id")
        if not voice_id:
            logger.error(f"Missing voice_id for Mistral assistant {assistant_id}")
            return None
        api_key = tts_config.get("api_key") or settings.MISTRAL_API_KEY
        return MistralTTS(
            model="voxtral-mini-tts-2603",
            voice_id=voice_id,
            api_key=api_key,
        )

    logger.error(f"Unsupported TTS model for assistant {assistant_id}")
    return None
