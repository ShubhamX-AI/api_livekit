import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from src.api.models.api_schemas import (
    CreateAssistant,
    NativeSTTConfig,
    UpdateAssistant,
)
from src.api.routes.assistant import (
    get_assistant_details,
    merge_interaction_config,
    update_assistant,
)
from src.core.agents.stt.factory import resolve_stt
from src.core.providers.keys import (
    SYSTEM_KEY_PLACEHOLDER,
    mask_api_key,
    mask_assistant_keys,
    provider_key_or_system,
)

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))
from migrate_stt_config import legacy_to_stt  # noqa: E402
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
            assistant_mode="pipeline",
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

    def test_masked_stt_key_rejected_for_every_provider(self):
        for provider in ("sarvam", "cartesia", "deepgram", "elevenlabs", "openai"):
            for masked in ("sk-t...5678", "****", SYSTEM_KEY_PLACEHOLDER):
                with self.subTest(provider=provider, masked=masked):
                    with self.assertRaises(ValidationError):
                        UpdateAssistant(
                            assistant_stt_model=provider,
                            assistant_stt_config={"api_key": masked},
                        )

    def test_real_keys_accepted(self):
        request = UpdateAssistant(
            assistant_tts_model="cartesia",
            assistant_tts_config={"voice_id": "v1", "api_key": "sk_cartesia_real_key"},
            assistant_llm_config={"provider": "openai", "api_key": "sk-proj-realkey"},
            assistant_stt_model="sarvam",
            assistant_stt_config={"api_key": "sk_sarvam_real_key"},
        )
        self.assertEqual(request.assistant_tts_config.api_key, "sk_cartesia_real_key")
        self.assertEqual(request.assistant_stt_config.api_key, "sk_sarvam_real_key")

    def test_omitted_keys_accepted(self):
        request = UpdateAssistant(
            assistant_tts_model="sarvam",
            assistant_tts_config={"speaker": "anushka"},
        )
        self.assertIsNone(request.assistant_tts_config.api_key)


class TestSTTConfig(unittest.TestCase):
    """assistant_stt_model / assistant_stt_config mirror the TTS pair."""

    def test_bare_model_gets_defaults_config(self):
        request = UpdateAssistant(assistant_stt_model="sarvam")
        self.assertEqual(request.assistant_stt_config.model, "saaras:v3")
        self.assertEqual(request.assistant_stt_config.language, "unknown")
        self.assertIsNone(request.assistant_stt_config.api_key)

    def test_discriminator_injected_from_model(self):
        request = UpdateAssistant(assistant_stt_model="native", assistant_stt_config={})
        self.assertIsInstance(request.assistant_stt_config, NativeSTTConfig)

    def test_config_without_model_rejected(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(assistant_stt_config={"type": "sarvam"})

    def test_retired_interaction_fields_rejected(self):
        for field in ("user_stt_provider", "stt_api_key"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    UpdateAssistant(assistant_interaction_config={field: "sarvam"})


class TestResolveSTT(unittest.TestCase):
    def test_unset_defaults_to_sarvam(self):
        assistant = SimpleNamespace(assistant_stt_model=None, assistant_stt_config=None)
        self.assertEqual(resolve_stt(assistant), ("sarvam", {}))

    def test_legacy_openai_maps_to_native(self):
        assistant = SimpleNamespace(assistant_stt_model="openai", assistant_stt_config=None)
        self.assertEqual(resolve_stt(assistant), ("native", {}))

    def test_no_key_anywhere_degrades_to_native(self):
        """An unauthenticated Sarvam tap would leave the call with no transcripts at all."""
        assistant = SimpleNamespace(
            assistant_id="assistant-1", assistant_stt_model="sarvam", assistant_stt_config={}
        )
        with patch("src.core.agents.stt.factory.settings.SARVAM_API_KEY", ""):
            self.assertEqual(resolve_stt(assistant), ("native", {}))

    def test_per_assistant_key_survives_missing_system_key(self):
        assistant = SimpleNamespace(
            assistant_id="assistant-1",
            assistant_stt_model="sarvam",
            assistant_stt_config={"api_key": "sk_x"},
        )
        with patch("src.core.agents.stt.factory.settings.SARVAM_API_KEY", ""):
            self.assertEqual(resolve_stt(assistant), ("sarvam", {"api_key": "sk_x"}))

    def test_returns_stored_config(self):
        config = {"type": "sarvam", "api_key": "sk_x", "language": "hi-IN"}
        assistant = SimpleNamespace(assistant_stt_model="sarvam", assistant_stt_config=config)
        self.assertEqual(resolve_stt(assistant), ("sarvam", config))

    def test_cascade_only_provider_without_key_degrades_to_native(self):
        for provider, env in (
            ("cartesia", "CARTESIA_API_KEY"),
            ("deepgram", "DEEPGRAM_API_KEY"),
            ("elevenlabs", "ELEVENLABS_API_KEY"),
        ):
            with self.subTest(provider=provider), patch(
                f"src.core.agents.stt.factory.settings.{env}", ""
            ):
                assistant = SimpleNamespace(
                    assistant_id="assistant-1",
                    assistant_stt_model=provider,
                    assistant_stt_config={},
                )
                self.assertEqual(resolve_stt(assistant), ("native", {}))

    def test_openai_stt_collapses_to_native_in_pipeline(self):
        """Same vendor, same model as the realtime model's own transcription — a second
        connection would buy nothing. Also keeps pre-migration 'openai' rows working."""
        assistant = SimpleNamespace(
            assistant_id="assistant-1",
            assistant_stt_model="openai",
            assistant_stt_config={"api_key": "sk_x"},
        )
        self.assertEqual(resolve_stt(assistant), ("native", {"api_key": "sk_x"}))

    def test_cascade_only_provider_with_config_key_is_kept(self):
        for provider in ("deepgram", "elevenlabs"):
            with self.subTest(provider=provider):
                assistant = SimpleNamespace(
                    assistant_id="assistant-1",
                    assistant_stt_model=provider,
                    assistant_stt_config={"api_key": "sk_x"},
                )
                model, config = resolve_stt(assistant)
                self.assertEqual(model, provider)
                self.assertEqual(config["api_key"], "sk_x")


class TestSTTBackfill(unittest.TestCase):
    """scripts/migrate_stt_config.py translation — the part that can lose a customer key."""

    def test_sarvam_key_carried_over(self):
        self.assertEqual(
            legacy_to_stt({"user_stt_provider": "sarvam", "stt_api_key": "sk_x"}),
            ("sarvam", {"type": "sarvam", "api_key": "sk_x"}),
        )

    def test_legacy_openai_alias(self):
        self.assertEqual(legacy_to_stt({"user_stt_provider": "openai"}), ("native", {"type": "native"}))

    def test_missing_fields_default_to_sarvam(self):
        self.assertEqual(legacy_to_stt({}), ("sarvam", {"type": "sarvam"}))

    def test_native_drops_stale_sarvam_key(self):
        self.assertEqual(
            legacy_to_stt({"user_stt_provider": "native", "stt_api_key": "sk_x"}),
            ("native", {"type": "native"}),
        )


class TestMaskApiKey(unittest.TestCase):
    def test_masks_named_field(self):
        masked = mask_api_key({"api_key": "sk_sarvam_1234"})
        self.assertEqual(masked["api_key"], "sk_s...1234")

    def test_absent_key_still_announces_system_fallback_by_default(self):
        self.assertEqual(mask_api_key({"voice_id": "v1"})["api_key"], SYSTEM_KEY_PLACEHOLDER)

    def test_short_key_fully_hidden(self):
        self.assertEqual(mask_api_key({"api_key": "short"})["api_key"], "****")


class TestMaskAssistantKeys(unittest.TestCase):
    """Every key-bearing config is masked; native STT is left alone."""

    def test_masks_all_key_bearing_configs(self):
        masked = mask_assistant_keys(
            {
                "assistant_tts_config": {"type": "cartesia", "api_key": "sk_cartesia_1234"},
                "assistant_stt_config": {"type": "sarvam", "api_key": "sk_sarvam_1234"},
                "assistant_llm_config": {"provider": "openai", "api_key": "sk-proj-12345678"},
            }
        )
        self.assertEqual(masked["assistant_tts_config"]["api_key"], "sk_c...1234")
        self.assertEqual(masked["assistant_stt_config"]["api_key"], "sk_s...1234")
        self.assertEqual(masked["assistant_llm_config"]["api_key"], "sk-p...5678")

    def test_native_stt_config_untouched(self):
        masked = mask_assistant_keys({"assistant_stt_config": {"type": "native"}})
        self.assertEqual(masked["assistant_stt_config"], {"type": "native"})

class TestProviderKeyOrSystem(unittest.TestCase):
    """A key belonging to one provider must never be sent to another (see 6e77183)."""

    def test_matching_provider_uses_assistant_key(self):
        config = {"provider": "openai", "api_key": "sk-proj-assistant"}
        self.assertEqual(
            provider_key_or_system(config, "openai", "openai", "sk-system"),
            "sk-proj-assistant",
        )

    def test_other_provider_falls_back_to_system_key(self):
        config = {"provider": "gemini", "api_key": "google-key"}
        self.assertEqual(
            provider_key_or_system(config, "gemini", "openai", "sk-system"),
            "sk-system",
        )

    def test_no_config_falls_back_to_system_key(self):
        self.assertEqual(provider_key_or_system(None, None, "openai", "sk-system"), "sk-system")


if __name__ == "__main__":
    unittest.main()
