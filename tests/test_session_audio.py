import unittest
from unittest.mock import patch

from src.core.agents.session import build_background_audio
from src.core.db.db_schemas import AssistantInteractionConfig


class TestSessionAudio(unittest.TestCase):
    @patch("src.core.agents.session.BackgroundAudioPlayer")
    @patch("src.core.agents.session.AudioConfig")
    def test_build_background_audio_uses_both_sounds_by_default(
        self,
        audio_config_mock,
        background_audio_player_mock,
    ):
        build_background_audio(AssistantInteractionConfig())

        self.assertEqual(audio_config_mock.call_count, 2)
        background_audio_player_mock.assert_called_once()

    @patch("src.core.agents.session.BackgroundAudioPlayer")
    @patch("src.core.agents.session.AudioConfig")
    def test_build_background_audio_can_disable_ambient_only(
        self,
        audio_config_mock,
        background_audio_player_mock,
    ):
        build_background_audio(
            AssistantInteractionConfig(
                background_sound_enabled=False,
                thinking_sound_enabled=True,
            )
        )

        self.assertEqual(audio_config_mock.call_count, 1)
        _, kwargs = background_audio_player_mock.call_args
        self.assertIsNone(kwargs["ambient_sound"])
        self.assertIsNotNone(kwargs["thinking_sound"])

    @patch("src.core.agents.session.BackgroundAudioPlayer")
    @patch("src.core.agents.session.AudioConfig")
    def test_build_background_audio_returns_none_when_both_disabled(
        self,
        audio_config_mock,
        background_audio_player_mock,
    ):
        result = build_background_audio(
            AssistantInteractionConfig(
                background_sound_enabled=False,
                thinking_sound_enabled=False,
            )
        )

        self.assertIsNone(result)
        audio_config_mock.assert_not_called()
        background_audio_player_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
