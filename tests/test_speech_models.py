"""Keep `model_support/speech.py` honest against the installed plugins.

That module states the accepted STT/TTS model ids as plain frozensets, because the API
container has no `livekit-agents` to read the plugins' own Literals from. The cost of writing a
set out by hand is that it can go stale silently — and a stale entry here has the same shape as
every other failure in this codebase: the config is accepted, the call connects, the stage
cannot start, and the caller hears nothing.

So this test reads the plugins (the test process has them) and compares. A `livekit-agents`
bump that adds, renames or drops a model id fails here instead of failing a call.

Where the platform set is deliberately wider than the plugin's Literal, the extra ids are
asserted explicitly rather than waved through — that keeps "we meant to add this" separate from
"this drifted".
"""

import unittest
from typing import get_args

from src.core.model_support.speech import (
    CARTESIA_STT_MODELS,
    DEEPGRAM_STT_MODELS,
    ELEVENLABS_RETIRED_TTS_MODELS,
    ELEVENLABS_STT_MODELS,
    ELEVENLABS_TTS_MODELS,
    OPENAI_STT_MODELS,
    SARVAM_STT_MODELS,
    SARVAM_TTS_MODELS,
    SARVAM_TTS_SPEAKERS,
    SARVAM_V2_SPEAKERS,
    SARVAM_V4_FLASH_ONLY_LANGUAGES,
    SARVAM_V4_FLASH_SPEAKERS,
    unsupported_sarvam_speaker_reason,
    unsupported_speech_model_reason,
)


def literal_values(literal) -> set[str]:
    """Flatten a Literal, including a Literal of Literals (Cartesia nests them)."""
    values = set()
    for arg in get_args(literal):
        if isinstance(arg, str):
            values.add(arg)
        else:
            values |= literal_values(arg)
    return values


class TestSTTModelSetsMatchThePlugins(unittest.TestCase):
    def test_sarvam(self):
        from livekit.plugins.sarvam.stt import MODEL_CONFIGS

        self.assertEqual(SARVAM_STT_MODELS, set(MODEL_CONFIGS))

    def test_cartesia(self):
        from livekit.plugins.cartesia.models import STTModels

        self.assertEqual(CARTESIA_STT_MODELS, literal_values(STTModels))

    def test_deepgram_is_a_subset_of_the_plugin_with_nothing_invented(self):
        """Unlike the other providers this one is a deliberate subset, not plugin parity.

        Deepgram stopped publishing a price for the nova-2, enhanced, base and hosted-whisper
        tiers, and this platform prices every call it accepts. So the allowlist is the set
        Deepgram still quotes — anything outside it is refused at the API rather than run at
        an unknown cost.
        """
        from livekit.plugins.deepgram.models import DeepgramModels, V2Models

        plugin = literal_values(DeepgramModels) | literal_values(V2Models)
        self.assertEqual(DEEPGRAM_STT_MODELS - plugin, set(), "ids the plugin cannot run")

    def test_every_allowlisted_deepgram_model_has_a_rate(self):
        """The reason the set is a subset: an accepted model with no rate bills as zero."""
        from src.core.pricing.rates import get_rate

        for model in DEEPGRAM_STT_MODELS:
            with self.subTest(model=model):
                self.assertIsNotNone(get_rate("stt_usage", "deepgram", model))

    def test_a_retired_deepgram_tier_is_refused(self):
        for model in ("nova-2", "nova-2-phonecall", "enhanced-general", "base", "whisper-large"):
            with self.subTest(model=model):
                self.assertIsNotNone(
                    unsupported_speech_model_reason("deepgram", model, stage="stt")
                )

    def test_elevenlabs(self):
        from livekit.plugins.elevenlabs.stt import ElevenLabsSTTModels

        self.assertEqual(ELEVENLABS_STT_MODELS, literal_values(ElevenLabsSTTModels))

    def test_openai_matches_the_sdk_minus_the_realtime_whisper_line(self):
        """gpt-realtime-whisper needs a client-side VAD this deployment cannot supply."""
        from openai.types import AudioModel

        sdk = literal_values(AudioModel)
        self.assertEqual(sdk - OPENAI_STT_MODELS, set())
        self.assertEqual(OPENAI_STT_MODELS - sdk, set())
        self.assertNotIn("gpt-realtime-whisper", OPENAI_STT_MODELS)


class TestTTSModelSetsMatchThePlugins(unittest.TestCase):
    def test_elevenlabs(self):
        from livekit.plugins.elevenlabs.models import TTSModels

        # The plugin still lists the two v1 models ElevenLabs retired; they are kept out on
        # purpose, and this keeps any other plugin addition from slipping past.
        self.assertEqual(
            ELEVENLABS_TTS_MODELS | ELEVENLABS_RETIRED_TTS_MODELS, literal_values(TTSModels)
        )
        self.assertEqual(ELEVENLABS_TTS_MODELS & ELEVENLABS_RETIRED_TTS_MODELS, set())

    def test_every_model_has_a_settings_entry_or_reads_everything(self):
        """A new model with no entry in the table would be allowed every setting."""
        from src.core.model_support.speech import ELEVENLABS_UNREAD_SETTINGS

        self.assertEqual(
            ELEVENLABS_TTS_MODELS - set(ELEVENLABS_UNREAD_SETTINGS), {"eleven_multilingual_v2"}
        )

    def test_the_default_elevenlabs_model_is_allowlisted(self):
        self.assertIn("eleven_v3", ELEVENLABS_TTS_MODELS)


class TestSarvamSpeakerRoster(unittest.TestCase):
    def test_the_roster_matches_the_pinned_model(self):
        from livekit.plugins.sarvam.tts import MODEL_SPEAKER_COMPATIBILITY

        from src.core.agents.tts.factory import SARVAM_TTS_MODEL

        self.assertEqual(
            SARVAM_TTS_SPEAKERS,
            set(MODEL_SPEAKER_COMPATIBILITY[SARVAM_TTS_MODEL]["all"]),
        )

    def test_the_v2_roster_shares_no_name_with_v3(self):
        """Which is why a copied speaker is the common mistake, and why it is rejected."""
        self.assertEqual(SARVAM_V2_SPEAKERS & SARVAM_TTS_SPEAKERS, set())

    def test_a_v2_speaker_is_rejected_by_name(self):
        reason = unsupported_sarvam_speaker_reason("anushka")
        self.assertIn("bulbul:v2 speaker", reason)

    def test_an_unknown_speaker_is_rejected(self):
        self.assertIn("not a bulbul:v3 speaker", unsupported_sarvam_speaker_reason("zaphod"))

    def test_a_v3_speaker_is_accepted(self):
        self.assertIsNone(unsupported_sarvam_speaker_reason("shubh"))

    def test_no_speaker_is_not_this_check_s_problem(self):
        self.assertIsNone(unsupported_sarvam_speaker_reason(None))


class TestSarvamV4FlashRoster(unittest.TestCase):
    def test_the_v4_only_languages_match_the_plugin(self):
        from src.core.agents.stt.lang import SARVAM_IN22_TTS_LANGUAGES

        self.assertEqual(SARVAM_V4_FLASH_ONLY_LANGUAGES, SARVAM_IN22_TTS_LANGUAGES)

    def test_the_roster_matches_the_plugin(self):
        from livekit.plugins.sarvam.tts import MODEL_SPEAKER_COMPATIBILITY

        self.assertEqual(
            SARVAM_V4_FLASH_SPEAKERS,
            set(MODEL_SPEAKER_COMPATIBILITY["bulbul:v4-flash"]["all"]),
        )

    def test_every_allowlisted_model_has_a_plugin_roster(self):
        from livekit.plugins.sarvam.tts import MODEL_SPEAKER_COMPATIBILITY

        self.assertEqual(SARVAM_TTS_MODELS - set(MODEL_SPEAKER_COMPATIBILITY), set())

    def test_the_v4_roster_shares_no_name_with_v3(self):
        self.assertEqual(SARVAM_V4_FLASH_SPEAKERS & SARVAM_TTS_SPEAKERS, set())

    def test_a_v4_speaker_is_accepted_on_v4(self):
        self.assertIsNone(unsupported_sarvam_speaker_reason("shubh_hi_customer", "bulbul:v4-flash"))

    def test_a_v3_name_on_v4_suggests_the_same_voice(self):
        reason = unsupported_sarvam_speaker_reason("shubh", "bulbul:v4-flash")
        self.assertIn("not a bulbul:v4-flash speaker", reason)
        self.assertIn("shubh_hi_customer", reason)
        self.assertNotIn("simran_", reason)

    def test_an_unknown_name_on_v4_is_rejected(self):
        self.assertIn(
            "not a bulbul:v4-flash speaker",
            unsupported_sarvam_speaker_reason("zaphod", "bulbul:v4-flash"),
        )

    def test_a_v4_name_on_v3_points_at_the_model_field(self):
        reason = unsupported_sarvam_speaker_reason("shubh_hi_customer", "bulbul:v3")
        self.assertIn("set model to 'bulbul:v4-flash'", reason)

    def test_the_longest_v4_name_fits_the_schema(self):
        from src.api.models.api_schemas.config.tts_config import SarvamTTSConfig

        longest = max(SARVAM_V4_FLASH_SPEAKERS, key=len)
        config = SarvamTTSConfig(model="bulbul:v4-flash", speaker=longest)
        self.assertEqual(config.speaker, longest)


class TestUnsupportedSpeechModelReason(unittest.TestCase):
    def test_a_typo_is_rejected_with_the_alternatives(self):
        reason = unsupported_speech_model_reason("deepgram", "nova-9", stage="stt")
        self.assertIn("nova-9", reason)
        self.assertIn("nova-3", reason)

    def test_a_real_model_passes(self):
        self.assertIsNone(unsupported_speech_model_reason("deepgram", "nova-3", stage="stt"))

    def test_the_two_stages_have_separate_tables(self):
        """ElevenLabs is in both, with families that must not be interchangeable."""
        self.assertIsNotNone(
            unsupported_speech_model_reason("elevenlabs", "eleven_v3", stage="stt")
        )
        self.assertIsNotNone(
            unsupported_speech_model_reason("elevenlabs", "scribe_v2", stage="tts")
        )

    def test_a_pinned_provider_has_nothing_to_check(self):
        """Cartesia TTS takes no model field — the pin in the factory is the allowlist."""
        self.assertIsNone(unsupported_speech_model_reason("cartesia", "sonic-9", stage="tts"))

    def test_no_model_named_is_fine(self):
        self.assertIsNone(unsupported_speech_model_reason("deepgram", None, stage="stt"))


if __name__ == "__main__":
    unittest.main()
