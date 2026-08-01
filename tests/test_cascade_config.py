"""Cascade mode: STT/LLM construction, schema rules, and per-component usage folding.

Cascade is the true STT -> LLM -> TTS pipeline (assistant_mode="cascade"). These
tests cover the parts that decide what actually gets built, without touching the network.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from pydantic import ValidationError

from livekit.agents.metrics.usage import (
    AgentSessionUsage,
    LLMModelUsage,
    STTModelUsage,
    TTSModelUsage,
)

from src.api.models.api_schemas import CreateAssistant, UpdateAssistant
from src.core.agents.llm import create_llm
from src.core.agents.stt import create_stt
from src.core.agents.usage import summarize_usage
from src.core.db.db_schemas import UsageRecord


def make_assistant(preferred_languages=None, **overrides):
    """Minimal stand-in for the Assistant document — the factories only read these."""
    fields = {
        "assistant_id": "assistant-1",
        "assistant_stt_model": None,
        "assistant_stt_config": None,
        "assistant_llm_config": None,
        "assistant_interaction_config": SimpleNamespace(
            preferred_languages=preferred_languages
        ),
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestCreateSTT(unittest.TestCase):
    def test_sarvam_defaults_are_multilingual(self):
        """Unset config must give auto-detect + code-mixing, the multilingual default."""
        stt = create_stt(
            make_assistant(assistant_stt_model="sarvam", assistant_stt_config={"api_key": "k"})
        )
        self.assertEqual(stt._opts.model, "saaras:v3")
        self.assertEqual(stt._opts.language, "unknown")  # auto-detect
        self.assertEqual(stt._opts.mode, "codemix")  # keeps code-switching intact

    def test_sarvam_config_overrides_defaults(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="sarvam",
                assistant_stt_config={
                    "api_key": "k",
                    "model": "saarika:v2.5",
                    "language": "hi-IN",
                    "mode": "transcribe",
                },
            )
        )
        self.assertEqual(stt._opts.model, "saarika:v2.5")
        self.assertEqual(stt._opts.language, "hi-IN")
        self.assertEqual(stt._opts.mode, "transcribe")

    def test_cartesia_model_is_pinned_not_defaulted(self):
        """The plugin default flipped to the English-only ink-2 in 1.5.15, so the
        43-language ink-whisper must be passed explicitly."""
        stt = create_stt(
            make_assistant(assistant_stt_model="cartesia", assistant_stt_config={"api_key": "k"})
        )
        self.assertEqual(stt._model, "ink-whisper")
        self.assertEqual(stt._language, "en")

    def test_cartesia_falls_back_to_preferred_language(self):
        """Cartesia cannot auto-detect, so an unpinned language must honour
        preferred_languages instead of silently transcribing a Hindi call as English."""
        stt = create_stt(
            make_assistant(
                assistant_stt_model="cartesia",
                assistant_stt_config={"api_key": "k"},
                preferred_languages=["hi", "en"],
            )
        )
        self.assertEqual(stt._language, "hi")

    def test_cartesia_explicit_language_beats_preferred(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="cartesia",
                assistant_stt_config={"api_key": "k", "language": "ta"},
                preferred_languages=["hi"],
            )
        )
        self.assertEqual(stt._language, "ta")

    def test_sarvam_ignores_preferred_languages_by_design(self):
        """Auto-detect already covers every language preferred_languages could list;
        pinning one would be worse for a caller who switches mid-call."""
        stt = create_stt(
            make_assistant(
                assistant_stt_model="sarvam",
                assistant_stt_config={"api_key": "k"},
                preferred_languages=["hi", "en"],
            )
        )
        self.assertEqual(stt._opts.language, "unknown")

    def test_unset_model_defaults_to_sarvam(self):
        stt = create_stt(make_assistant(assistant_stt_config={"api_key": "k"}))
        self.assertEqual(stt._opts.model, "saaras:v3")

    def test_native_is_rejected(self):
        """"native" means the realtime model transcribes itself; cascade has none."""
        self.assertIsNone(create_stt(make_assistant(assistant_stt_model="native")))

    def test_unknown_provider_is_rejected(self):
        self.assertIsNone(create_stt(make_assistant(assistant_stt_model="deepgram")))

    def test_missing_key_is_rejected(self):
        with mock.patch("src.core.agents.stt.factory.settings.SARVAM_API_KEY", ""):
            self.assertIsNone(
                create_stt(make_assistant(assistant_stt_model="sarvam", assistant_stt_config={}))
            )
        with mock.patch("src.core.agents.stt.factory.settings.CARTESIA_API_KEY", ""):
            self.assertIsNone(
                create_stt(make_assistant(assistant_stt_model="cartesia", assistant_stt_config={}))
            )


class TestCreateLLM(unittest.TestCase):
    def test_defaults_to_gpt_41(self):
        llm = create_llm(make_assistant(assistant_llm_config={"api_key": "k"}))
        self.assertEqual(llm.model, "gpt-4.1")

    def test_model_override(self):
        llm = create_llm(
            make_assistant(assistant_llm_config={"api_key": "k", "model": "gpt-4.1-mini"})
        )
        self.assertEqual(llm.model, "gpt-4.1-mini")

    def test_non_openai_provider_rejected(self):
        self.assertIsNone(
            create_llm(make_assistant(assistant_llm_config={"provider": "gemini", "api_key": "k"}))
        )

    def test_missing_key_rejected(self):
        with mock.patch("src.core.agents.llm.factory.settings.OPENAI_API_KEY", ""):
            self.assertIsNone(create_llm(make_assistant(assistant_llm_config={})))


class TestCascadeSchemaRules(unittest.TestCase):
    BASE = {
        "assistant_name": "A",
        "assistant_description": "d",
        "assistant_prompt": "p",
        "assistant_mode": "cascade",
        "assistant_tts_model": "cartesia",
        "assistant_tts_config": {"voice_id": "v1"},
    }

    def test_cascade_accepted_with_stt_and_tts(self):
        request = CreateAssistant(**self.BASE, assistant_stt_model="sarvam")
        self.assertEqual(request.assistant_mode, "cascade")
        # A bare model still materializes a defaults-only config.
        self.assertEqual(request.assistant_stt_config.model, "saaras:v3")

    def test_cascade_accepts_cartesia_stt(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="cartesia",
            assistant_stt_config={"language": "hi"},
        )
        self.assertEqual(request.assistant_stt_config.type, "cartesia")
        self.assertEqual(request.assistant_stt_config.language, "hi")

    def test_cascade_rejects_native_stt(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(**self.BASE, assistant_stt_model="native")

    def test_cascade_rejects_non_openai_provider(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(**self.BASE, assistant_llm_config={"provider": "gemini"})

    def test_cascade_requires_tts(self):
        without_tts = {k: v for k, v in self.BASE.items() if not k.startswith("assistant_tts")}
        with self.assertRaises(ValidationError):
            CreateAssistant(**without_tts)

    def test_update_to_cascade_rejects_native_stt(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(assistant_mode="cascade", assistant_stt_model="native")

    def test_update_to_cascade_accepts_sarvam(self):
        request = UpdateAssistant(assistant_mode="cascade", assistant_stt_model="sarvam")
        self.assertEqual(request.assistant_stt_config.mode, "codemix")

    def test_pipeline_and_realtime_still_valid(self):
        """The two existing modes must be untouched by the cascade rules."""
        pipeline = CreateAssistant(
            **{**self.BASE, "assistant_mode": "pipeline"},
            assistant_stt_model="native",  # legal in pipeline mode
        )
        self.assertEqual(pipeline.assistant_mode, "pipeline")
        realtime = CreateAssistant(
            assistant_name="A",
            assistant_description="d",
            assistant_prompt="p",
            assistant_mode="realtime",
            assistant_llm_config={"provider": "gemini"},
        )
        self.assertEqual(realtime.assistant_mode, "realtime")


class TestStoredCascadeGuards(unittest.TestCase):
    """The schema's cascade rules only fire when a request names the mode. A PATCH that
    omits it must still be checked against the stored row, or the assistant is accepted
    and then silently fails to start."""

    def test_schema_alone_does_not_catch_an_omitted_mode(self):
        # Documents exactly why the route-level guard has to exist.
        request = UpdateAssistant(assistant_llm_config={"provider": "gemini"})
        self.assertEqual(request.assistant_llm_config.provider, "gemini")

    def test_route_rejects_gemini_on_a_stored_cascade_assistant(self):
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="cascade", assistant_stt_model="sarvam")
        with self.assertRaises(HTTPException) as ctx:
            assistant_route.enforce_cascade_constraints(
                stored, {"assistant_llm_config": {"provider": "gemini"}}, new_mode=None
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_route_rejects_native_stt_on_a_stored_cascade_assistant(self):
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="cascade", assistant_stt_model="sarvam")
        with self.assertRaises(HTTPException):
            assistant_route.enforce_cascade_constraints(
                stored, {"assistant_stt_model": "native"}, new_mode=None
            )

    def test_route_allows_a_valid_cascade_patch(self):
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="cascade", assistant_stt_model="sarvam")
        assistant_route.enforce_cascade_constraints(
            stored,
            {"assistant_llm_config": {"provider": "openai", "model": "gpt-4.1-mini"}},
            new_mode=None,
        )

    def test_route_ignores_non_cascade_assistants(self):
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="pipeline", assistant_stt_model="native")
        assistant_route.enforce_cascade_constraints(
            stored, {"assistant_llm_config": {"provider": "gemini"}}, new_mode=None
        )


class TestSummarizeUsage(unittest.TestCase):
    def _usage(self):
        return AgentSessionUsage(
            model_usage=[
                LLMModelUsage(
                    provider="openai",
                    model="gpt-4.1-mini",
                    input_tokens=100,
                    input_text_tokens=90,
                    output_tokens=40,
                    output_text_tokens=40,
                ),
                # A second entry for the same component: totals must sum across them.
                LLMModelUsage(
                    provider="openai", model="gpt-4o-mini", input_tokens=10, output_tokens=5
                ),
                TTSModelUsage(
                    provider="cartesia", model="sonic-3", characters_count=250, audio_duration=12.5
                ),
                STTModelUsage(provider="sarvam", model="saaras:v3", audio_duration=31.25),
            ]
        )

    def test_sums_across_entries_per_component(self):
        metered = summarize_usage(SimpleNamespace(usage=self._usage()))
        self.assertEqual(metered["llm_total_tokens"], 155)  # (100+40) + (10+5)
        self.assertEqual(metered["llm_input_text_tokens"], 90)
        self.assertEqual(metered["tts_characters_count"], 250)
        self.assertEqual(metered["tts_audio_duration"], 12.5)
        self.assertEqual(metered["stt_audio_duration"], 31.25)

    def test_records_model_names(self):
        metered = summarize_usage(SimpleNamespace(usage=self._usage()))
        self.assertEqual(metered["llm_model"], "gpt-4.1-mini, gpt-4o-mini")
        self.assertEqual(metered["stt_model"], "saaras:v3")

    def test_every_key_is_a_usage_record_field(self):
        """session.py splats this dict into UsageRecord(**metered) — a stray key would
        break every call's usage record, so pin the contract here."""
        metered = summarize_usage(SimpleNamespace(usage=self._usage()))
        self.assertEqual(set(metered) - set(UsageRecord.model_fields), set())

    def test_degrades_to_zeros_instead_of_raising(self):
        metered = summarize_usage(SimpleNamespace())  # no .usage at all
        self.assertEqual(metered["llm_total_tokens"], 0)
        self.assertEqual(metered["stt_audio_duration"], 0.0)
        self.assertIsNone(metered["stt_model"])

    def test_empty_usage_reports_no_models(self):
        metered = summarize_usage(SimpleNamespace(usage=AgentSessionUsage(model_usage=[])))
        self.assertIsNone(metered["llm_model"])
        self.assertEqual(metered["tts_characters_count"], 0)


if __name__ == "__main__":
    unittest.main()
