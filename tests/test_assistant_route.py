import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from src.api.models.api_schemas import SYSTEM_KEY_PLACEHOLDER, UpdateAssistant
from src.api.routes.assistant import (
    get_assistant_details,
    mask_api_key,
    merge_interaction_config,
    update_assistant,
)
from src.core.db.db_schemas import AssistantInteractionConfig


class QueryField:
    def __eq__(self, other):
        return other


class TestAssistantRoute(unittest.IsolatedAsyncioTestCase):
    async def test_update_assistant_merges_partial_interaction_config(self):
        request = UpdateAssistant(
            assistant_interaction_config={
                "thinking_sound_enabled": False,
            }
        )
        current_user = SimpleNamespace(user_email="user@example.com")
        assistant = SimpleNamespace(
            assistant_interaction_config=AssistantInteractionConfig(
                speaks_first=True,
                filler_words=True,
                silence_reprompts=True,
                silence_reprompt_interval=12.0,
                silence_max_reprompts=3,
                background_sound_enabled=True,
                thinking_sound_enabled=True,
            ),
            update=AsyncMock(),
        )

        assistant_model = SimpleNamespace(
            assistant_id=QueryField(),
            assistant_created_by_email=QueryField(),
            find_one=AsyncMock(return_value=assistant),
        )

        with patch("src.api.routes.assistant.Assistant", assistant_model):
            response = await update_assistant(
                assistant_id="assistant-1",
                request=request,
                current_user=current_user,
            )

        self.assertTrue(response.success)
        assistant.update.assert_awaited_once()
        update_doc = assistant.update.await_args.args[0]["$set"]
        self.assertEqual(update_doc["assistant_interaction_config"]["speaks_first"], True)
        self.assertEqual(update_doc["assistant_interaction_config"]["filler_words"], True)
        self.assertEqual(
            update_doc["assistant_interaction_config"]["background_sound_enabled"],
            True,
        )
        self.assertEqual(
            update_doc["assistant_interaction_config"]["thinking_sound_enabled"],
            False,
        )

    def test_merge_interaction_config_accepts_model_or_dict(self):
        merged_from_model = merge_interaction_config(
            AssistantInteractionConfig(background_sound_enabled=False),
            {"thinking_sound_enabled": False},
        )
        merged_from_dict = merge_interaction_config(
            {"speaks_first": True},
            {"background_sound_enabled": False},
        )

        self.assertEqual(merged_from_model["background_sound_enabled"], False)
        self.assertEqual(merged_from_model["thinking_sound_enabled"], False)
        self.assertEqual(merged_from_dict["speaks_first"], True)
        self.assertEqual(merged_from_dict["background_sound_enabled"], False)

    async def test_get_assistant_details_masks_llm_config_api_key(self):
        current_user = SimpleNamespace(user_email="user@example.com")
        assistant = SimpleNamespace(
            model_dump=lambda exclude=None: {
                "assistant_id": "assistant-1",
                "assistant_name": "Masked Bot",
                "assistant_llm_config": {"api_key": "sk-test-12345678"},
                "assistant_tts_config": None,
            }
        )

        assistant_model = SimpleNamespace(
            assistant_id=QueryField(),
            assistant_created_by_email=QueryField(),
            assistant_is_active=QueryField(),
            find_one=AsyncMock(return_value=assistant),
        )

        with patch("src.api.routes.assistant.Assistant", assistant_model):
            response = await get_assistant_details(
                assistant_id="assistant-1",
                current_user=current_user,
            )

        self.assertTrue(response.success)
        self.assertEqual(
            response.data["assistant_llm_config"]["api_key"],
            "sk-t...5678",
        )


class TestMaskedKeyGuard(unittest.TestCase):
    """A masked key read from GET /details must never be writable back."""

    def test_masked_tts_key_rejected_for_every_provider(self):
        configs = {
            "cartesia": {"voice_id": "v1"},
            "sarvam": {"speaker": "anushka"},
            "elevenlabs": {"voice_id": "v1"},
            "mistral": {"voice_id": "v1"},
        }
        for provider, base in configs.items():
            for masked in ("sk-t...5678", "****", SYSTEM_KEY_PLACEHOLDER):
                with self.subTest(provider=provider, masked=masked):
                    with self.assertRaises(ValidationError):
                        UpdateAssistant(
                            assistant_tts_model=provider,
                            assistant_tts_config={**base, "api_key": masked},
                        )

    def test_masked_llm_key_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(assistant_llm_config={"provider": "openai", "api_key": "sk-t...5678"})

    def test_masked_stt_key_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(assistant_interaction_config={"stt_api_key": SYSTEM_KEY_PLACEHOLDER})

    def test_real_keys_accepted(self):
        request = UpdateAssistant(
            assistant_tts_model="cartesia",
            assistant_tts_config={"voice_id": "v1", "api_key": "sk_cartesia_real_key"},
            assistant_llm_config={"provider": "openai", "api_key": "sk-proj-realkey"},
            assistant_interaction_config={"stt_api_key": "sk_sarvam_real_key"},
        )
        self.assertEqual(request.assistant_tts_config.api_key, "sk_cartesia_real_key")
        self.assertEqual(request.assistant_interaction_config.stt_api_key, "sk_sarvam_real_key")

    def test_omitted_keys_accepted(self):
        request = UpdateAssistant(
            assistant_tts_model="sarvam",
            assistant_tts_config={"speaker": "anushka"},
        )
        self.assertIsNone(request.assistant_tts_config.api_key)


class TestMaskApiKey(unittest.TestCase):
    def test_masks_named_field(self):
        masked = mask_api_key({"stt_api_key": "sk_sarvam_1234"}, field="stt_api_key")
        self.assertEqual(masked["stt_api_key"], "sk_s...1234")

    def test_only_if_present_does_not_invent_field(self):
        masked = mask_api_key({"speaks_first": True}, field="stt_api_key", only_if_present=True)
        self.assertNotIn("stt_api_key", masked)

    def test_absent_key_still_announces_system_fallback_by_default(self):
        self.assertEqual(mask_api_key({"voice_id": "v1"})["api_key"], SYSTEM_KEY_PLACEHOLDER)

    def test_short_key_fully_hidden(self):
        self.assertEqual(mask_api_key({"api_key": "short"})["api_key"], "****")


if __name__ == "__main__":
    unittest.main()
