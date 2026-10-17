"""The TTS settings migration: which stored rows it rewrites, and how."""

import unittest

from scripts.migrate_tts_settings import tts_fixes


class TestTtsFixes(unittest.TestCase):
    def test_a_retired_elevenlabs_model_is_moved(self):
        self.assertEqual(
            tts_fixes("elevenlabs", {"model": "eleven_monolingual_v1", "voice_settings": {"speed": 1.1}}),
            ({"assistant_tts_config.model": "eleven_multilingual_v2"}, []),
        )

    def test_unread_settings_are_removed_on_the_default_model(self):
        """No `model` stored means eleven_v3, which reads stability only."""
        _, unset = tts_fixes("elevenlabs", {"voice_settings": {"stability": 0.5, "speed": 1.2, "style": None}})
        self.assertEqual(unset, ["assistant_tts_config.voice_settings.speed"])

    def test_v4_flash_temperature_is_removed(self):
        self.assertEqual(
            tts_fixes("sarvam", {"model": "bulbul:v4-flash", "temperature": 0.3}),
            ({}, ["assistant_tts_config.temperature"]),
        )

    def test_clean_rows_are_left_alone(self):
        self.assertEqual(tts_fixes("sarvam", {"model": "bulbul:v3", "temperature": 0.3}), ({}, []))
        self.assertEqual(
            tts_fixes("elevenlabs", {"model": "eleven_multilingual_v2", "voice_settings": {"speed": 1.2}}),
            ({}, []),
        )
        self.assertEqual(tts_fixes("cartesia", {"speed": 1.0}), ({}, []))


if __name__ == "__main__":
    unittest.main()
