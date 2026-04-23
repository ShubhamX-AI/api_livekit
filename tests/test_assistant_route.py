import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.api.models.api_schemas import UpdateAssistant
from src.api.routes.assistant import (
    get_assistant_details,
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


if __name__ == "__main__":
    unittest.main()
