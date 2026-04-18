import unittest

from src.api.models.api_schemas import (
    AssistantInteractionConfigSchema,
    CreateAssistant,
    UpdateAssistant,
)


class TestAssistantSchemas(unittest.TestCase):
    def test_interaction_config_defaults_enable_both_sound_flags(self):
        config = AssistantInteractionConfigSchema()

        self.assertTrue(config.background_sound_enabled)
        self.assertTrue(config.thinking_sound_enabled)

    def test_create_assistant_accepts_sound_flags(self):
        assistant = CreateAssistant(
            assistant_name="Support Bot",
            assistant_description="Test assistant",
            assistant_prompt="You are helpful.",
            assistant_llm_mode="pipeline",
            assistant_tts_model="cartesia",
            assistant_tts_config={"voice_id": "voice-1"},
            assistant_interaction_config={
                "background_sound_enabled": False,
                "thinking_sound_enabled": True,
            },
        )

        self.assertFalse(
            assistant.assistant_interaction_config.background_sound_enabled
        )
        self.assertTrue(
            assistant.assistant_interaction_config.thinking_sound_enabled
        )

    def test_update_assistant_accepts_independent_sound_toggle(self):
        assistant = UpdateAssistant(
            assistant_interaction_config={
                "thinking_sound_enabled": False,
            }
        )

        self.assertEqual(
            assistant.assistant_interaction_config.model_dump(exclude_unset=True),
            {"thinking_sound_enabled": False},
        )


if __name__ == "__main__":
    unittest.main()
