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
            make_assistant(
                assistant_stt_model="sarvam", assistant_stt_config={"api_key": "k"}
            )
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
            make_assistant(
                assistant_stt_model="cartesia", assistant_stt_config={"api_key": "k"}
            )
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
        """ "native" means the realtime model transcribes itself; cascade has none."""
        self.assertIsNone(create_stt(make_assistant(assistant_stt_model="native")))

    def test_unknown_provider_is_rejected(self):
        self.assertIsNone(create_stt(make_assistant(assistant_stt_model="whisper")))

    def test_deepgram_defaults_to_multilingual_nova3(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram", assistant_stt_config={"api_key": "k"}
            )
        )
        self.assertEqual(stt._opts.model, "nova-3")

    def test_deepgram_model_and_language_override(self):
        # nova, not flux: flux runs on a different Deepgram class entirely — see
        # TestDeepgramFamilyDispatch.
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram",
                assistant_stt_config={
                    "api_key": "k",
                    "model": "nova-2",
                    "language": "multi",
                    "enable_diarization": True,
                },
            )
        )
        self.assertEqual(stt._opts.model, "nova-2")
        self.assertEqual(stt._opts.language, "multi")
        self.assertTrue(stt._opts.enable_diarization)

    def test_deepgram_falls_back_to_preferred_language(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram",
                assistant_stt_config={"api_key": "k"},
                preferred_languages=["hi", "en"],
            )
        )
        self.assertEqual(stt._opts.language, "hi")

    def test_deepgram_explicit_language_beats_preferred(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram",
                assistant_stt_config={"api_key": "k", "language": "hi"},
                preferred_languages=["en"],
            )
        )
        self.assertEqual(stt._opts.language, "hi")

    def test_deepgram_optional_knobs_switched_off_by_default(self):
        """When diarization/keyterm are omitted they must not leak into the request as
        truthy — otherwise every Deepgram call would silently turn them on."""
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram", assistant_stt_config={"api_key": "k"}
            )
        )
        self.assertFalse(stt._opts.enable_diarization)
        self.assertEqual(stt._opts.keyterm, [])

    def test_deepgram_keyterm_forwarded(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="deepgram",
                assistant_stt_config={"api_key": "k", "keyterm": "Vyom"},
            )
        )
        self.assertIn("Vyom", stt._opts.keyterm)

    def test_elevenlabs_defaults_to_scribe_v2_realtime(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="elevenlabs", assistant_stt_config={"api_key": "k"}
            )
        )
        self.assertEqual(stt._opts.model_id, "scribe_v2_realtime")

    def test_elevenlabs_config_override(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="elevenlabs",
                assistant_stt_config={
                    "api_key": "k",
                    "model": "scribe_v2",
                    "language_code": "hi",
                    "no_verbatim": True,
                },
            )
        )
        self.assertEqual(stt._opts.model_id, "scribe_v2")
        self.assertEqual(stt._opts.language_code, "hi")
        self.assertTrue(stt._opts.no_verbatim)

    def test_elevenlabs_language_code_from_preferred_languages(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="elevenlabs",
                assistant_stt_config={"api_key": "k"},
                preferred_languages=["hi", "en"],
            )
        )
        self.assertEqual(stt._opts.language_code, "hi")

    def test_elevenlabs_omits_language_when_unset(self):
        """No language_code and no preferred_languages → the plugin stays auto-detect
        (~190 languages). The module sends `language_code` upstream only when it is set, so
        `None` is the auto-detect signal, not a literal `null`."""
        stt = create_stt(
            make_assistant(
                assistant_stt_model="elevenlabs", assistant_stt_config={"api_key": "k"}
            )
        )
        self.assertIsNone(stt._opts.language_code)

    def test_elevenlabs_no_verbatim_defaults_off(self):
        stt = create_stt(
            make_assistant(
                assistant_stt_model="elevenlabs", assistant_stt_config={"api_key": "k"}
            )
        )
        self.assertFalse(stt._opts.no_verbatim)

    def test_missing_key_is_rejected(self):
        with mock.patch("src.core.agents.stt.factory.settings.SARVAM_API_KEY", ""):
            self.assertIsNone(
                create_stt(
                    make_assistant(
                        assistant_stt_model="sarvam", assistant_stt_config={}
                    )
                )
            )
        with mock.patch("src.core.agents.stt.factory.settings.CARTESIA_API_KEY", ""):
            self.assertIsNone(
                create_stt(
                    make_assistant(
                        assistant_stt_model="cartesia", assistant_stt_config={}
                    )
                )
            )
        with mock.patch("src.core.agents.stt.factory.settings.DEEPGRAM_API_KEY", ""):
            self.assertIsNone(
                create_stt(
                    make_assistant(
                        assistant_stt_model="deepgram", assistant_stt_config={}
                    )
                )
            )
        with mock.patch("src.core.agents.stt.factory.settings.ELEVENLABS_API_KEY", ""):
            self.assertIsNone(
                create_stt(
                    make_assistant(
                        assistant_stt_model="elevenlabs", assistant_stt_config={}
                    )
                )
            )
        with mock.patch("src.core.agents.stt.factory.settings.OPENAI_API_KEY", ""):
            self.assertIsNone(
                create_stt(
                    make_assistant(assistant_stt_model="openai", assistant_stt_config={})
                )
            )


class TestOpenAISTT(unittest.TestCase):
    def _stt(self, preferred_languages=None, **config):
        return create_stt(
            make_assistant(
                preferred_languages=preferred_languages,
                assistant_stt_model="openai",
                assistant_stt_config={"api_key": "k", **config},
            )
        )

    def test_defaults_stream_over_the_realtime_socket(self):
        """The plugin default is batch REST — a live call needs the streaming path."""
        stt = self._stt()
        self.assertEqual(stt._opts.model, "gpt-4o-mini-transcribe")
        self.assertTrue(stt.capabilities.streaming)
        self.assertTrue(stt.capabilities.interim_results)

    def test_use_realtime_false_falls_back_to_batch(self):
        self.assertFalse(self._stt(use_realtime=False).capabilities.streaming)

    def test_language_defaults_to_english(self):
        self.assertEqual(self._stt()._opts.language, "en")

    def test_falls_back_to_preferred_language(self):
        self.assertEqual(self._stt(preferred_languages=["hi"])._opts.language, "hi")

    def test_explicit_language_beats_preferred(self):
        self.assertEqual(
            self._stt(preferred_languages=["hi"], language="ta")._opts.language, "ta"
        )

    def test_detect_language_blanks_the_pinned_language(self):
        """The plugin expresses auto-detect as an empty language code."""
        stt = self._stt(preferred_languages=["hi"], detect_language=True)
        self.assertTrue(stt._opts.detect_language)
        self.assertEqual(stt._opts.language, "")

    def test_optional_knobs_stay_unset_by_default(self):
        stt = self._stt()
        self.assertFalse(stt._opts.prompt)
        self.assertFalse(stt._opts.noise_reduction_type)

    def test_optional_knobs_forwarded(self):
        stt = self._stt(
            model="whisper-1", prompt="Acme Corp", noise_reduction_type="far_field"
        )
        self.assertEqual(stt._opts.prompt, "Acme Corp")
        self.assertEqual(stt._opts.noise_reduction_type, "far_field")

    def test_realtime_whisper_is_rejected(self):
        """No server-side endpointing: the plugin would need a silero VAD we don't ship."""
        self.assertIsNone(self._stt(model="gpt-realtime-whisper"))


class TestCreateLLM(unittest.TestCase):
    def test_defaults_to_gpt_41(self):
        llm = create_llm(make_assistant(assistant_llm_config={"api_key": "k"}))
        self.assertEqual(llm.model, "gpt-4.1")

    def test_model_override(self):
        llm = create_llm(
            make_assistant(
                assistant_llm_config={"api_key": "k", "model": "gpt-4.1-mini"}
            )
        )
        self.assertEqual(llm.model, "gpt-4.1-mini")

    def test_non_openai_provider_rejected(self):
        self.assertIsNone(
            create_llm(
                make_assistant(
                    assistant_llm_config={"provider": "gemini", "api_key": "k"}
                )
            )
        )

    def test_generation_knobs_forwarded(self):
        llm = create_llm(
            make_assistant(
                assistant_llm_config={
                    "api_key": "k",
                    "model": "gpt-5-mini",
                    "temperature": 0.2,
                    "max_output_tokens": 400,
                    "reasoning_effort": "medium",
                    "service_tier": "flex",
                    "verbosity": "low",
                    "tool_choice": "required",
                    "parallel_tool_calls": False,
                }
            )
        )
        opts = llm._opts
        self.assertEqual(opts.temperature, 0.2)
        self.assertEqual(opts.max_output_tokens, 400)
        self.assertEqual(opts.service_tier, "flex")
        self.assertEqual(opts.verbosity, "low")
        self.assertEqual(opts.tool_choice, "required")
        self.assertEqual(opts.parallel_tool_calls, False)
        self.assertEqual(opts.reasoning.effort, "medium")

    def test_omitted_knobs_keep_defaults(self):
        llm = create_llm(make_assistant(assistant_llm_config={"api_key": "k"}))
        opts = llm._opts
        # NotGiven — the SDK applies its own defaults.
        from livekit.agents.types import NOT_GIVEN

        self.assertIs(opts.temperature, NOT_GIVEN)
        self.assertIs(opts.max_output_tokens, NOT_GIVEN)

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

    def test_cascade_accepts_deepgram_stt(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="deepgram",
            assistant_stt_config={"model": "nova-3", "language": "multi"},
        )
        self.assertEqual(request.assistant_stt_config.type, "deepgram")
        self.assertEqual(request.assistant_stt_config.model, "nova-3")
        self.assertEqual(request.assistant_stt_config.language, "multi")

    def test_cascade_accepts_elevenlabs_stt(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="elevenlabs",
            assistant_stt_config={"no_verbatim": True},
        )
        self.assertEqual(request.assistant_stt_config.type, "elevenlabs")
        self.assertEqual(request.assistant_stt_config.no_verbatim, True)

    def test_cascade_accepts_openai_stt(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="openai",
            assistant_stt_config={"model": "gpt-4o-transcribe", "detect_language": True},
        )
        self.assertEqual(request.assistant_stt_config.type, "openai")
        self.assertEqual(request.assistant_stt_config.model, "gpt-4o-transcribe")
        self.assertTrue(request.assistant_stt_config.detect_language)
        self.assertTrue(request.assistant_stt_config.use_realtime)

    def test_cascade_rejects_native_stt(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(**self.BASE, assistant_stt_model="native")

    def test_cascade_rejects_non_openai_provider(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(**self.BASE, assistant_llm_config={"provider": "gemini"})

    def test_cascade_accepts_documented_openai_model(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="sarvam",
            assistant_llm_config={"model": "gpt-4.1-mini"},
        )
        self.assertEqual(request.assistant_llm_config.model, "gpt-4.1-mini")

    def test_cascade_rejects_unknown_openai_model(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(
                **self.BASE,
                assistant_stt_model="sarvam",
                assistant_llm_config={"model": "gpt-4.1-quantum"},
            )

    def test_cascade_accepts_llm_generation_knobs(self):
        request = CreateAssistant(
            **self.BASE,
            assistant_stt_model="sarvam",
            assistant_llm_config={
                "model": "gpt-5-mini",
                "temperature": 0.3,
                "max_output_tokens": 512,
                "reasoning_effort": "low",
                "service_tier": "flex",
                "verbosity": "medium",
                "tool_choice": "required",
                "parallel_tool_calls": False,
            },
        )
        cfg = request.assistant_llm_config
        self.assertEqual(cfg.temperature, 0.3)
        self.assertEqual(cfg.max_output_tokens, 512)
        self.assertEqual(cfg.reasoning_effort, "low")

    def test_cascade_rejects_unknown_llm_config_key(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(
                **self.BASE,
                assistant_stt_model="sarvam",
                assistant_llm_config={
                    "model": "gpt-4.1-mini",
                    "frequency_penalty": 1.0,
                },
            )

    def test_tts_config_rejects_unknown_keys(self):
        cfg = {
            **self.BASE,
            "assistant_stt_model": "sarvam",
            "assistant_tts_config": {"voice_id": "v1", "bogus": 1},
        }
        with self.assertRaises(ValidationError):
            CreateAssistant(**cfg)

    def test_cascade_requires_tts(self):
        without_tts = {
            k: v for k, v in self.BASE.items() if not k.startswith("assistant_tts")
        }
        with self.assertRaises(ValidationError):
            CreateAssistant(**without_tts)

    def test_update_to_cascade_rejects_native_stt(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(assistant_mode="cascade", assistant_stt_model="native")

    def test_update_to_cascade_accepts_sarvam(self):
        request = UpdateAssistant(
            assistant_mode="cascade", assistant_stt_model="sarvam"
        )
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
    """The schema's mode rules only fire when a request names the mode. A PATCH that
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
            assistant_route.enforce_stored_mode_constraints(
                stored, {"assistant_llm_config": {"provider": "gemini"}}, new_mode=None
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_route_rejects_native_stt_on_a_stored_cascade_assistant(self):
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="cascade", assistant_stt_model="sarvam")
        with self.assertRaises(HTTPException):
            assistant_route.enforce_stored_mode_constraints(
                stored, {"assistant_stt_model": "native"}, new_mode=None
            )

    def test_route_allows_a_valid_cascade_patch(self):
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(assistant_mode="cascade", assistant_stt_model="sarvam")
        assistant_route.enforce_stored_mode_constraints(
            stored,
            {"assistant_llm_config": {"provider": "openai", "model": "gpt-4.1-mini"}},
            new_mode=None,
        )

    def test_route_rejects_gemini_on_a_stored_pipeline_assistant(self):
        """Pipeline is OpenAI-only too, so the same guard applies outside cascade."""
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="pipeline", assistant_stt_model="native"
        )
        with self.assertRaises(HTTPException) as ctx:
            assistant_route.enforce_stored_mode_constraints(
                stored, {"assistant_llm_config": {"provider": "gemini"}}, new_mode=None
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_route_allows_an_unrelated_pipeline_patch(self):
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="pipeline", assistant_stt_model="native"
        )
        assistant_route.enforce_stored_mode_constraints(
            stored, {"assistant_name": "renamed"}, new_mode=None
        )

    def test_route_rejects_switch_to_cascade_over_stored_gemini(self):
        """The request alone looks fine — only the merge with the stored row is invalid."""
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="pipeline",
            assistant_stt_model="sarvam",
            assistant_llm_config={"provider": "gemini"},
        )
        with self.assertRaises(HTTPException) as ctx:
            assistant_route.enforce_stored_mode_constraints(
                stored, {"assistant_mode": "cascade"}, new_mode="cascade"
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_route_rejects_switch_to_cascade_over_stored_realtime_model(self):
        from fastapi import HTTPException

        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="pipeline",
            assistant_stt_model="sarvam",
            assistant_llm_config={"provider": "openai", "model": "gpt-realtime-1.5"},
        )
        with self.assertRaises(HTTPException) as ctx:
            assistant_route.enforce_stored_mode_constraints(
                stored, {"assistant_mode": "cascade"}, new_mode="cascade"
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_route_lets_the_same_request_fix_the_stored_config(self):
        """The 400 above must be escapable in one request, not a dead end."""
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="pipeline",
            assistant_stt_model="sarvam",
            assistant_llm_config={"provider": "gemini"},
        )
        assistant_route.enforce_stored_mode_constraints(
            stored,
            {
                "assistant_mode": "cascade",
                "assistant_llm_config": {"provider": "openai", "model": "gpt-4.1-mini"},
            },
            new_mode="cascade",
        )

    def test_route_honours_an_explicitly_cleared_llm_config(self):
        """Leaving realtime nulls the stored config; the old Gemini row must not be merged."""
        from src.api.routes import assistant as assistant_route

        stored = SimpleNamespace(
            assistant_mode="realtime",
            assistant_stt_model="native",
            assistant_llm_config={"provider": "gemini"},
        )
        assistant_route.enforce_stored_mode_constraints(
            stored,
            {"assistant_mode": "pipeline", "assistant_llm_config": None},
            new_mode="pipeline",
        )


class TestCreateTTS(unittest.TestCase):
    def test_elevenlabs_absent_voice_settings_stays_unset(self):
        """An existing ElevenLabs assistant with no voice_settings must keep passing
        NOT_GIVEN (not None) — the client's is_given(None) is True and would crash on
        dataclasses.asdict(None) at the first synthesis."""
        from src.core.agents.tts.factory import create_tts

        tts = create_tts(
            make_assistant(
                assistant_tts_model="elevenlabs",
                assistant_tts_config={
                    "voice_id": "v",
                    "api_key": "k",
                    "model": "eleven_v3",
                },
            )
        )
        from livekit.agents.types import NOT_GIVEN

        self.assertIs(tts._opts.voice_settings, NOT_GIVEN)

    def test_elevenlabs_present_voice_settings_is_forwarded(self):
        from src.core.agents.tts.factory import create_tts

        tts = create_tts(
            make_assistant(
                assistant_tts_model="elevenlabs",
                assistant_tts_config={
                    "voice_id": "v",
                    "api_key": "k-key",
                    "voice_settings": {
                        "stability": 0.7,
                        "similarity_boost": 0.8,
                        "style": 0.3,
                        "speed": 1.2,
                        "use_speaker_boost": True,
                    },
                },
            )
        )
        vs = tts._opts.voice_settings
        self.assertEqual(
            (
                vs.stability,
                vs.similarity_boost,
                vs.style,
                vs.speed,
                vs.use_speaker_boost,
            ),
            (0.7, 0.8, 0.3, 1.2, True),
        )

    def test_cartesia_speed_and_volume_forwarded(self):
        from src.core.agents.tts.factory import create_tts

        tts = create_tts(
            make_assistant(
                assistant_tts_model="cartesia",
                assistant_tts_config={
                    "voice_id": "v",
                    "api_key": "k",
                    "speed": 1.5,
                    "volume": 0.8,
                },
            )
        )
        self.assertEqual(tts._opts.speed, 1.5)
        self.assertEqual(tts._opts.volume, 0.8)

    def test_sarvam_pace_and_temperature_forwarded(self):
        from src.core.agents.tts.factory import create_tts

        tts = create_tts(
            make_assistant(
                assistant_tts_model="sarvam",
                assistant_tts_config={
                    "speaker": "shubh",
                    "api_key": "k",
                    "pace": 1.2,
                    "temperature": 0.5,
                },
            )
        )
        self.assertEqual(tts._opts.pace, 1.2)
        self.assertEqual(tts._opts.temperature, 0.5)

    def test_sarvam_omitted_target_language_falls_back_to_en_in(self):
        """The schema stores null, so the factory's own fallback has to apply. A concrete
        schema default here would silently synthesize the wrong language."""
        from src.api.models.api_schemas.config.tts_config import SarvamTTSConfig
        from src.core.agents.tts.factory import create_tts

        stored = SarvamTTSConfig(speaker="shubh", api_key="k").model_dump()
        self.assertIsNone(stored["target_language_code"])
        tts = create_tts(
            make_assistant(assistant_tts_model="sarvam", assistant_tts_config=stored)
        )
        self.assertEqual(tts._opts.target_language_code, "en-IN")

    def test_cartesia_speed_rejects_preset_strings(self):
        """sonic-3 takes a float only — the plugin raises on "fast", so the schema must
        reject it at create time rather than at the first synthesis."""
        from src.api.models.api_schemas.config.tts_config import CartesiaTTSConfig

        with self.assertRaises(ValidationError):
            CartesiaTTSConfig(voice_id="v", speed="fast")

    def test_partial_voice_settings_uses_the_documented_defaults(self):
        from src.core.agents.tts.factory import create_tts

        tts = create_tts(
            make_assistant(
                assistant_tts_model="elevenlabs",
                assistant_tts_config={
                    "voice_id": "v",
                    "api_key": "k",
                    "voice_settings": {"style": 0.4},
                },
            )
        )
        vs = tts._opts.voice_settings
        self.assertEqual((vs.stability, vs.similarity_boost, vs.style), (0.5, 0.5, 0.4))

    def test_missing_key_returns_none_instead_of_raising(self):
        """Every provider must take the `return None` path, which entrypoint() handles.
        ElevenLabs used to raise ValueError straight out of create_tts."""
        from src.core.agents.tts import factory as tts_factory

        cases = [
            ("cartesia", {"voice_id": "v"}, "CARTESIA_API_KEY"),
            ("sarvam", {"speaker": "shubh"}, "SARVAM_API_KEY"),
            ("elevenlabs", {"voice_id": "v"}, "ELEVENLABS_API_KEY"),
            ("mistral", {"voice_id": "v"}, "MISTRAL_API_KEY"),
        ]
        for model, config, env_key in cases:
            with self.subTest(model=model):
                with mock.patch.object(tts_factory.settings, env_key, ""):
                    self.assertIsNone(
                        tts_factory.create_tts(
                            make_assistant(
                                assistant_tts_model=model, assistant_tts_config=config
                            )
                        )
                    )


class TestDeepgramFamilyDispatch(unittest.TestCase):
    """flux and nova speak different Deepgram APIs; neither class validates the model at
    construction, so a flux ID on the v1 class only fails when the socket opens."""

    def _stt(self, **config):
        return create_stt(
            make_assistant(
                assistant_stt_model="deepgram",
                assistant_stt_config={"api_key": "k", **config},
            )
        )

    def test_nova_uses_the_v1_class(self):
        self.assertEqual(type(self._stt(model="nova-3")).__name__, "STT")

    def test_flux_uses_the_v2_class(self):
        for model in ("flux-general-en", "flux-general-multi"):
            with self.subTest(model=model):
                self.assertEqual(type(self._stt(model=model)).__name__, "STTv2")

    def test_flux_drops_diarization_instead_of_crashing(self):
        stt = self._stt(model="flux-general-multi", enable_diarization=True)
        self.assertEqual(type(stt).__name__, "STTv2")


class TestSarvamTTSRanges(unittest.TestCase):
    """Schema bounds must match Sarvam's own, or the API 400s on a value we accepted."""

    def test_provider_limits_are_accepted(self):
        from src.api.models.api_schemas.config.tts_config import SarvamTTSConfig

        for field, value in (
            ("pace", 0.3),
            ("pace", 3.0),
            ("temperature", 0.01),
            ("speech_sample_rate", 8000),
        ):
            with self.subTest(field=field, value=value):
                SarvamTTSConfig(speaker="shubh", **{field: value})

    def test_out_of_range_values_are_rejected(self):
        from src.api.models.api_schemas.config.tts_config import SarvamTTSConfig

        for field, value in (
            ("pace", 0.2),
            ("pace", 3.1),
            ("temperature", 0.0),
            ("speech_sample_rate", 20000),  # between two supported rates, still invalid
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValidationError):
                    SarvamTTSConfig(speaker="shubh", **{field: value})


class TestModeGuardrails(unittest.TestCase):
    """Combinations the runtime cannot execute must fail at the API, not at call time."""

    def _create(self, **overrides):
        payload = {
            "assistant_name": "A",
            "assistant_description": "d",
            "assistant_prompt": "p",
            "assistant_mode": "pipeline",
            "assistant_tts_model": "cartesia",
            "assistant_tts_config": {"voice_id": "v"},
        }
        payload.update(overrides)
        return CreateAssistant(**payload)

    def test_pipeline_rejects_gemini(self):
        with self.assertRaises(ValidationError) as ctx:
            self._create(assistant_llm_config={"provider": "gemini"})
        self.assertIn("realtime", str(ctx.exception))

    def test_pipeline_accepts_openai(self):
        created = self._create(assistant_llm_config={"provider": "openai"})
        self.assertEqual(created.assistant_llm_config.provider, "openai")

    def test_pipeline_rejects_a_cascade_chat_model(self):
        """gpt-4.1 speaks the Responses API, not the Realtime API — it cannot connect."""
        with self.assertRaises(ValidationError):
            self._create(assistant_llm_config={"model": "gpt-4.1"})

    def test_pipeline_accepts_a_realtime_model(self):
        created = self._create(assistant_llm_config={"model": "gpt-realtime-1.5"})
        self.assertEqual(created.assistant_llm_config.model, "gpt-realtime-1.5")

    def test_realtime_still_accepts_gemini_and_free_form_models(self):
        created = CreateAssistant(
            assistant_name="A",
            assistant_description="d",
            assistant_prompt="p",
            assistant_mode="realtime",
            assistant_llm_config={
                "provider": "gemini",
                "model": "gemini-3.1-flash-live-preview",
            },
        )
        self.assertEqual(created.assistant_llm_config.provider, "gemini")

    def test_realtime_rejects_a_chat_model_on_openai(self):
        with self.assertRaises(ValidationError):
            CreateAssistant(
                assistant_name="A",
                assistant_description="d",
                assistant_prompt="p",
                assistant_mode="realtime",
                assistant_llm_config={"provider": "openai", "model": "gpt-4.1"},
            )

    def test_update_rejects_gemini_when_the_request_names_pipeline(self):
        with self.assertRaises(ValidationError):
            UpdateAssistant(
                assistant_mode="pipeline",
                assistant_llm_config={"provider": "gemini"},
            )


class TestUnknownConfigKeys(unittest.TestCase):
    """Every provider config block is strict — a typo is a 422, not a silent no-op."""

    def test_mistral_tts_rejects_unknown_keys(self):
        from src.api.models.api_schemas.config.tts_config import MistralTTSConfig

        with self.assertRaises(ValidationError):
            MistralTTSConfig(voice_id="v", speed=1.5)

    def test_every_stt_config_rejects_unknown_keys(self):
        from src.api.models.api_schemas.config import stt_config as stt_schemas

        cases = [
            (stt_schemas.NativeSTTConfig, {}),
            (stt_schemas.SarvamSTTConfig, {}),
            (stt_schemas.CartesiaSTTConfig, {}),
            (stt_schemas.DeepgramSTTConfig, {}),
            (stt_schemas.ElevenLabsSTTConfig, {}),
            (stt_schemas.OpenAISTTConfig, {}),
        ]
        for model_cls, base in cases:
            with self.subTest(model=model_cls.__name__):
                with self.assertRaises(ValidationError):
                    model_cls(**base, enable_diarisation=True)


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
                    provider="openai",
                    model="gpt-4o-mini",
                    input_tokens=10,
                    output_tokens=5,
                ),
                TTSModelUsage(
                    provider="cartesia",
                    model="sonic-3",
                    characters_count=250,
                    audio_duration=12.5,
                ),
                STTModelUsage(
                    provider="sarvam", model="saaras:v3", audio_duration=31.25
                ),
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
        metered = summarize_usage(
            SimpleNamespace(usage=AgentSessionUsage(model_usage=[]))
        )
        self.assertIsNone(metered["llm_model"])
        self.assertEqual(metered["tts_characters_count"], 0)


if __name__ == "__main__":
    unittest.main()
