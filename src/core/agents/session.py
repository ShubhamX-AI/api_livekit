from dotenv import load_dotenv
from collections import deque
from livekit import rtc
from livekit.agents import (
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    room_io,
    BackgroundAudioPlayer,
    AudioConfig,
    function_tool,
    RunContext,
    TurnHandlingOptions,
    NOT_GIVEN,
)
from openai.types.beta.realtime.session import TurnDetection
from livekit.plugins import sarvam as sarvam_plugin
from livekit.plugins.openai import realtime
from livekit.plugins.google import realtime as google_realtime
from openai.types.realtime import AudioTranscription
from openai.types.realtime.realtime_truncation_retention_ratio import (
    RealtimeTruncationRetentionRatio,
    TokenLimits,
)
import os
import asyncio
import json
from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import logger, setup_logging, set_room_context
from src.core.agents.dynamic_assistant import DynamicAssistant
from src.core.agents.inbound_context import resolve_inbound_context
from src.core.agents.session_lifecycle import CallReadinessGate, RecordingManager
from src.core.agents.tts import create_tts, maintain_sarvam_connection
from src.core.agents.stt import run_sarvam_parallel_stt
from src.core.agents.utils import render_prompt
from src.core.agents.voice_features import SilenceWatchdogController, FillerController, HoldController, InputGuardController
from src.core.agents.tool_builder import build_tools_from_db
from src.core.db.database import Database
from src.core.db.db_schemas import Assistant, AudioAsset, InboundContextStrategy, UsageRecord, CallRecord
from src.services.livekit.livekit_svc import LiveKitService
from src.services.storage import s3_audio
from livekit.agents.utils.audio import audio_frames_from_file
from livekit.agents.metrics import UsageCollector


setup_logging()
load_dotenv(override=True)

# Platform default applied when assistant_interaction_config.max_call_duration_minutes is unset.
DEFAULT_MAX_CALL_DURATION_MINUTES = 30.0


# Helper to build background audio player based on interaction config
def build_background_audio(interaction_config) -> BackgroundAudioPlayer | None:
    ambient_sound = None
    if getattr(interaction_config, "background_sound_enabled", True):
        ambient_path = os.path.join(settings.AUDIO_DIR, "office-ambience_48k.wav")
        ambient_sound = AudioConfig(ambient_path, volume=0.6)

    thinking_sound = None
    if getattr(interaction_config, "thinking_sound_enabled", True):
        typing_path = os.path.join(settings.AUDIO_DIR, "typing-sound_48k.wav")
        thinking_sound = AudioConfig(typing_path, volume=0.7)

    if ambient_sound is None and thinking_sound is None:
        return None

    return BackgroundAudioPlayer(
        ambient_sound=ambient_sound,
        thinking_sound=thinking_sound,
    )


# Play a referenced audio asset as the greeting instead of generating it with the model.
# Returns the spoken transcript on success, or None so the caller falls back to the model greeting.
async def play_prerecorded_greeting(session, audio_id, allow_interruptions) -> str | None:
    asset = await AudioAsset.find_one(
        AudioAsset.audio_id == audio_id,
        AudioAsset.is_active == True,
    )
    if not asset:
        logger.warning("Greeting audio_id %s not found or inactive; using model greeting", audio_id)
        return None

    # transcript goes to the chat context so the model knows it already greeted
    transcript = asset.transcript or ""
    tmp_path = None
    try:
        tmp_path = await asyncio.to_thread(s3_audio.download_to_tempfile, asset.s3_key)
        handle = session.say(
            transcript,
            audio=audio_frames_from_file(tmp_path, sample_rate=48000, num_channels=1),
            allow_interruptions=allow_interruptions,
            add_to_chat_ctx=True,
        )
        # wait for playout: the file is streamed lazily, so keep it until reading finishes
        await handle.wait_for_playout()
        logger.info("Start instruction strategy | mode=prerecorded_greeting_audio | audio=%s", audio_id)
        return transcript
    except Exception as e:
        logger.error(f"Prerecorded greeting failed, falling back to model greeting: {e}", exc_info=True)
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


async def entrypoint(ctx: JobContext):
    # Ensure database connection
    try:
        await Database.connect_db()
    except Exception as e:
        logger.error(f"Failed to connect to database in worker: {e}")
        return

    # Retrieve agent ID from room name
    room_name = ctx.room.name
    assistant_id = room_name.split("_", 1)[0]
    set_room_context(room_name)
    logger.info(f"Agent session starting | room: {room_name} | identifier: {assistant_id}")

    # Fetch assistant from DB
    assistant = await Assistant.find_one(Assistant.assistant_id == assistant_id)
    if not assistant:
        logger.error(f"No assistant found for identifier: {assistant_id}")
        return

    logger.info(f"Loaded assistant config: {assistant.assistant_name} (ID: {assistant.assistant_id})")
    is_realtime = assistant.assistant_llm_mode == "realtime"

    # Extract metadata from job metadata
    to_number = "Web Call"
    job_metadata = {}
    render_data = {}
    if ctx.job.metadata:
        try:
            job_metadata = json.loads(ctx.job.metadata)
            to_number = job_metadata.get("to_number", "Web Call")
            logger.info(f"Extracted to_number from job metadata: {to_number}")
        except Exception as e:
            logger.warning(f"Failed to parse job metadata or process placeholders: {e}")

    # Text-only web chat: skip STT, TTS, recording. Validated upstream against realtime mode.
    is_web_call = job_metadata.get("call_type") == "web"
    is_text_only = is_web_call and job_metadata.get("text_only") is True

    if job_metadata:
        render_data = {**job_metadata, "call": job_metadata}

    # Resolve inbound context if applicable
    if job_metadata.get("call_type") == "inbound":
        strategy_id = job_metadata.get("inbound_context_strategy_id")
        if strategy_id:
            strategy = await InboundContextStrategy.find_one(
                InboundContextStrategy.strategy_id == strategy_id,
                InboundContextStrategy.strategy_created_by_email == assistant.assistant_created_by_email,
                InboundContextStrategy.strategy_is_active == True,
            )
            if strategy:
                context = await resolve_inbound_context(
                    strategy=strategy,
                    assistant_id=assistant.assistant_id,
                    assistant_name=assistant.assistant_name,
                    user_email=assistant.assistant_created_by_email,
                    room_name=room_name,
                    job_metadata=job_metadata,
                )
                if context is not None:
                    render_data = {**render_data, "context": context}
            else:
                logger.warning(
                    f"Inbound context strategy '{strategy_id}' not found or inactive; continuing with default prompt"
                )

    # Render metadata placeholders in prompts
    if assistant.assistant_prompt:
        assistant.assistant_prompt = render_prompt(assistant.assistant_prompt, render_data)
    if assistant.assistant_start_instruction:
        assistant.assistant_start_instruction = render_prompt(
            assistant.assistant_start_instruction, render_data,
        )
    if render_data:
        logger.info("Successfully processed metadata placeholders in assistant instructions")


    interaction_config = assistant.assistant_interaction_config
    # Filler words require external TTS (session.say), disabled in realtime mode.
    # Voice-only features (filler, silence reprompts, background/thinking sounds) all
    # off for text-only chats — no audio in or out.
    filler_words_enabled = bool(interaction_config.filler_words) and not is_realtime and not is_text_only
    silence_reprompts_enabled = bool(interaction_config.silence_reprompts) and not is_text_only
    background_sound_enabled = bool(getattr(interaction_config, "background_sound_enabled", True)) and not is_text_only
    thinking_sound_enabled = bool(getattr(interaction_config, "thinking_sound_enabled", True)) and not is_text_only
    logger.info(
        "Assistant voice features | "
        f"filler_words={filler_words_enabled} | "
        f"silence_reprompts={silence_reprompts_enabled} | "
        f"background_sound={background_sound_enabled} | "
        f"thinking_sound={thinking_sound_enabled} | "
        f"realtime={is_realtime}"
    )

    # --- Call Readiness & Recording ---
    is_exotel_outbound = job_metadata.get("call_service") == "exotel"
    livekit_services = LiveKitService()
    gate = CallReadinessGate(is_exotel_outbound)
    recorder = RecordingManager(livekit_services, room_name, assistant_id)

    # Bounded queue serializes transcript DB writes off the audio hot path.
    # put_nowait on the event handler never blocks; single consumer drains async.
    _transcript_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def _transcript_worker():
        while True:
            fn = await _transcript_queue.get()
            try:
                await fn()
            except Exception as e:
                logger.error(f"Transcript write failed | room={room_name}: {e}")
            finally:
                _transcript_queue.task_done()

    transcript_worker = asyncio.create_task(_transcript_worker())

    # Start recording immediately for non-Exotel calls. Text-only web chats have no audio.
    if not is_exotel_outbound and not is_text_only:
        asyncio.create_task(recorder.start_once())

    # --- Load Tools ---
    tools = []
    if assistant.tool_ids:
        try:
            tools = await build_tools_from_db(
                assistant.tool_ids,
                user_email=assistant.assistant_created_by_email,
                room_name=room_name,
                assistant_id=assistant_id,
            )
            logger.info(f"Loaded {len(tools)} tool(s) for assistant {assistant.assistant_id}")
        except Exception as e:
            logger.error(f"Failed to load tools: {e}", exc_info=True)

    # Persist usage metrics at call end
    async def _persist_usage():
        try:
            summary = usage_collector.get_summary()
            telephony_provider = job_metadata.get("call_service") or job_metadata.get("service")
            if job_metadata.get("call_type") == "web":
                telephony_provider = None

            # Compute call duration from CallRecord
            call_duration = 0.0
            call_record = await CallRecord.find_one(CallRecord.room_name == room_name)
            if call_record:
                ended_at = datetime.now(timezone.utc)
                duration_start = call_record.answered_at or call_record.started_at
                call_duration = (ended_at - duration_start).total_seconds() / 60

            # LLM vendor, recorded for both modes. Resolved once at model build (see below).
            llm_realtime_provider = realtime_provider

            usage = UsageRecord(
                room_name=room_name,
                assistant_id=assistant_id,
                user_email=assistant.assistant_created_by_email,
                llm_mode=assistant.assistant_llm_mode,
                llm_realtime_provider=llm_realtime_provider,
                tts_provider=assistant.assistant_tts_model if not is_realtime else None,
                call_service=telephony_provider,
                llm_input_audio_tokens=summary.llm_input_audio_tokens,
                llm_input_text_tokens=summary.llm_input_text_tokens,
                llm_input_cached_audio_tokens=summary.llm_input_cached_audio_tokens,
                llm_input_cached_text_tokens=summary.llm_input_cached_text_tokens,
                llm_output_audio_tokens=summary.llm_output_audio_tokens,
                llm_output_text_tokens=summary.llm_output_text_tokens,
                llm_total_tokens=summary.llm_prompt_tokens + summary.llm_completion_tokens,
                tts_characters_count=summary.tts_characters_count,
                tts_audio_duration=summary.tts_audio_duration,
                call_duration_minutes=call_duration,
            )
            await usage.insert()
            logger.info(
                f"Usage persisted | room={room_name} | "
                f"llm_tokens={usage.llm_total_tokens} | "
                f"tts_chars={usage.tts_characters_count}"
            )
        except Exception as e:
            logger.error(f"Failed to persist usage record: {e}", exc_info=True)

    _sarvam_stop = asyncio.Event()

    # Watchdog/tools stamp a reason before teardown persists it.
    _end_reason: str = "natural"
    _max_duration_task: asyncio.Task | None = None

    # Single teardown path used by both EndCallTool and participant disconnect
    async def _flush_and_end_call(delay: float = 0.0):
        nonlocal call_end_triggered
        call_end_triggered = True  # Block duplicate from disconnect handler
        _sarvam_stop.set()
        if _max_duration_task is not None and not _max_duration_task.done():
            _max_duration_task.cancel()
        if input_guard is not None:
            await input_guard.aclose()
        # Mute all room audio inputs immediately — prevents STT from
        # processing any new speech during the TTS playout delay window
        # await livekit_services.mute_room_audio_inputs(ctx.room.name)
        if delay > 0:
            await asyncio.sleep(delay)  # Let TTS audio finish streaming to egress
        # Drain transcript queue before ending (max 3s).
        # call_end_triggered is already True, so no new items will be enqueued.
        try:
            await asyncio.wait_for(_transcript_queue.join(), timeout=3.0)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for pending transcripts")
        transcript_worker.cancel()
        await asyncio.gather(transcript_worker, return_exceptions=True)
        await _persist_usage()
        try:
            rec = await CallRecord.find_one(CallRecord.room_name == ctx.room.name)
            if rec and rec.call_end_reason is None:
                rec.call_end_reason = _end_reason
                await rec.save()
        except Exception as e:
            logger.error(f"Failed to persist call_end_reason: {e}")
        try:
            await livekit_services.end_call(room_name=ctx.room.name, assistant_id=assistant_id)
        except Exception as e:
            logger.error(f"end_call failed — call may stay stuck in 'answered' | room={ctx.room.name}: {e}", exc_info=True)
        try:
            await livekit_services.delete_room(room_name=ctx.room.name)
        except Exception as e:
            logger.error(f"delete_room failed | room={ctx.room.name}: {e}")

    # Custom end_call tool — LLM speaks goodbye first, tool waits for playout before stopping recording
    if getattr(assistant, "assistant_end_call_enabled", False):
        trigger_phrase = (getattr(assistant, "assistant_end_call_trigger_phrase", None) or "").strip()
        agent_message = (getattr(assistant, "assistant_end_call_agent_message", None) or "Thank you, goodbye!").strip()

        trigger_condition = (
            f"ONLY call this when the user clearly says: '{trigger_phrase}'."
            if trigger_phrase else
            "Call this when the user clearly wants to end the call."
        )
        tool_description = f"End the current call. {trigger_condition}"

        @function_tool(description=tool_description)
        async def end_call(_ctx: RunContext):
            """Wait for the LLM's goodbye speech to finish, then end the call."""
            # Small buffer for recording egress to finalize audio capture
            asyncio.create_task(_flush_and_end_call(delay=1.5))
            return f"Say this to the user: '{agent_message}'"

        tools.append(end_call)
        logger.info(f"Custom end_call tool enabled for assistant {assistant.assistant_id}")

    # --- Build Agent & LLM ---
    agent_instance = DynamicAssistant(
        room=ctx.room,
        instructions=assistant.assistant_prompt,
        start_instruction=assistant.assistant_start_instruction or "Greet the user Professionally",
        tools=tools,
    )

    # LLM vendor is orthogonal to mode. `is_realtime` = model speaks its own audio
    # (no external TTS); provider = which vendor. Default per mode keeps old assistants working.
    llm_config = assistant.assistant_llm_config or {}
    _default_provider = "gemini" if is_realtime else "openai"
    realtime_provider = (llm_config.get("provider") or _default_provider).lower()
    # Set inside the half-cascade branches when Sarvam parallel STT is active.
    _use_sarvam_stt = False

    if is_realtime:
        # Full realtime mode: single model handles STT + LLM + TTS (audio out).
        if realtime_provider == "gemini":
            llm = google_realtime.RealtimeModel(
                model=llm_config.get("model", "gemini-3.1-flash-live-preview"),
                voice=llm_config.get("voice", "Puck"),
                modalities=["AUDIO"],
                instructions=assistant.assistant_prompt,
                api_key=llm_config.get("api_key") or settings.GOOGLE_API_KEY,
            )
        elif realtime_provider == "openai":
            llm = realtime.RealtimeModel(
                model=llm_config.get("model", "gpt-realtime-1.5"),
                voice=llm_config.get("voice", "marin"),
                modalities=["audio"],
                turn_detection=TurnDetection(
                    type="semantic_vad",
                    eagerness="high",
                    create_response=True,
                    interrupt_response=False,
                ),
                truncation=RealtimeTruncationRetentionRatio(
                    type="retention_ratio",
                    retention_ratio=0.75,
                    token_limits=TokenLimits(post_instructions=8000),
                ),
                api_key=llm_config.get("api_key") or settings.OPENAI_API_KEY,
            )
        else:
            logger.error(f"Unsupported realtime provider: {realtime_provider}")
            return

        logger.info(f"Realtime mode | provider={realtime_provider} | model={llm_config.get('model')}")
    else:
        # Half-cascade mode: realtime model emits TEXT, separate TTS speaks the audio.
        _langs = interaction_config.preferred_languages or []
        # Phone calls (Exotel SIP) feed lossy G.711 narrowband audio (300-3400 Hz).
        # OpenAI's `far_field` noise-reduction model is trained on this signature;
        # `near_field` assumes close-mic/headset and degrades phone transcription.
        _is_phone_call = job_metadata.get("call_type") != "web"
        _noise_reduction = "far_field" if _is_phone_call else "near_field"
        _phone_audio_note = (
            "Audio is from a live telephone call (G.711 narrowband, ~8 kHz, lossy). "
            "Expect static, line hum, codec artifacts, and muffled consonants. "
            "Do NOT treat noise as speech. "
            if _is_phone_call else ""
        )
        _stt_prompt = (
            f"{'Expected language(s): ' + ', '.join(_langs) + '. ' if _langs else ''}"
            f"{_phone_audio_note}"
            "This is a live customer support voice call. The speaker may use any language or mix languages mid-sentence. "
            "Transcribe ONLY what is actually spoken, in the speaker's natural script for that language. "
            "If audio is unclear, silent, or unintelligible — output [inaudible]. NEVER guess or fabricate words. "
            "For mixed speech, transcribe each word in its own correct native script. "
            "Do NOT romanize. Do NOT translate. Do NOT switch to a different language than what was spoken. "
            "Use natural punctuation. Skip filler sounds like um, uh, hmm."
        )

        # Sarvam Saras v3 handles user STT in parallel (default, "sarvam"). The alternative
        # ("native") lets the conversational LLM transcribe itself — provider-agnostic. When
        # Sarvam is active we skip the LLM's own transcription to avoid dual writes and save cost.
        # Text-only chats have no audio, so treat as "no parallel STT" — the SDK's own
        # conversation events carry the user text.
        _use_sarvam_stt = (
            not is_text_only
            and (interaction_config.user_stt_provider or "sarvam") == "sarvam"
        )
        _openai_transcription = None if _use_sarvam_stt else AudioTranscription(
            model="gpt-4o-transcribe",
            prompt=_stt_prompt,
        )

        if realtime_provider == "openai":
            llm = realtime.RealtimeModel(
                model=llm_config.get("model", "gpt-realtime-1.5"),
                input_audio_transcription=_openai_transcription,
                input_audio_noise_reduction=_noise_reduction,
                turn_detection=TurnDetection(
                    type="semantic_vad",
                    eagerness="high",
                    create_response=True,
                    interrupt_response=False,  # Don't interrupt LLM response mid-generation; let it finish and handle turn-taking in the agent logic instead
                ),
                modalities=["text"],
                truncation=RealtimeTruncationRetentionRatio(
                    type="retention_ratio",
                    retention_ratio=0.75,
                    token_limits=TokenLimits(post_instructions=8000),
                ),
                api_key=llm_config.get("api_key") or settings.OPENAI_API_KEY,
            )
        elif realtime_provider == "gemini":
            # Gemini realtime emitting TEXT only; external TTS speaks it. Sarvam parallel STT
            # (default) taps the track independently, so ask Gemini for its own user transcript
            # only when Sarvam is not doing it.
            from google.genai import types as genai_types

            _gemini_user_transcription = (
                None if _use_sarvam_stt else genai_types.AudioTranscriptionConfig()
            )
            llm = google_realtime.RealtimeModel(
                model=llm_config.get("model", "gemini-3.1-flash-live-preview"),
                modalities=["TEXT"],
                instructions=assistant.assistant_prompt,
                input_audio_transcription=_gemini_user_transcription,
                api_key=llm_config.get("api_key") or settings.GOOGLE_API_KEY,
            )
        else:
            logger.error(f"Unsupported pipeline provider: {realtime_provider}")
            return
        logger.info("Half-cascade mode | llm=%s | tts=%s", realtime_provider, assistant.assistant_tts_model)

    # --- Build TTS (pipeline mode only) ---
    tts = None
    if not is_realtime and not is_text_only:
        tts = create_tts(assistant)
        if tts is None:
            return
        if hasattr(tts, "prewarm"):
            tts.prewarm()

    # --- Session Setup ---
    # Text-only chats reuse the realtime branch shape (no TTS, no audio knobs).
    if is_realtime or is_text_only:
        session = AgentSession(llm=llm)
    else:
        session = AgentSession(
            llm=llm,
            tts=tts,
            # preemptive_generation=True,  # Deprecated in favor of turn_detection options below
            use_tts_aligned_transcript=True,
            aec_warmup_duration=1.0,  # seconds
            turn_handling=TurnHandlingOptions(
                turn_detection="realtime_llm",
                endpointing={
                    "mode": "dynamic",
                    "min_delay": 0.3,
                    "max_delay": 1.0,
                },
                interruption={
                    "mode": "adaptive",
                    "min_duration": 2.5,
                    "min_words": 0,
                    "discard_audio_if_uninterruptible": True,
                    "false_interruption_timeout": 0.2,
                    "resume_false_interruption": True,
                },
        )
        )

    # --- Usage Tracking ---
    usage_collector = UsageCollector()

    @session.on("metrics_collected")
    def on_metrics(event):
        usage_collector.collect(event.metrics)

    context_turns = deque(maxlen=4)
    user_is_speaking = False
    silence_watchdog = (
        SilenceWatchdogController(
            session=session,
            logger=logger,
            reprompt_interval_sec=interaction_config.silence_reprompt_interval,
            max_reprompts=interaction_config.silence_max_reprompts,
            use_llm_for_speech=is_realtime,
        ) if silence_reprompts_enabled else None
    )
    filler_controller = FillerController(session=session, context_turns=context_turns) if filler_words_enabled else None
    hold_controller = HoldController(
        logger=logger,
        session=session,
        silence_watchdog=silence_watchdog,
        filler_controller=filler_controller,
    )
    input_guard = None if (is_realtime or is_text_only) else InputGuardController(
        session=session,
        logger=logger,
        window_sec=getattr(interaction_config, "input_guard_window_sec", 3.0),
    )

    # Background audio
    background_audio = build_background_audio(interaction_config)

    # Text-only web chats turn off audio I/O on both sides and publish agent replies as
    # transcription text on the lk.chat topic. Regular web calls keep audio plus text input.
    logger.info(
        f"Session input mode | call_type={job_metadata.get('call_type')} | "
        f"text_input={is_web_call} | text_only={is_text_only}"
    )

    room_options = room_io.RoomOptions(
        text_input=is_web_call,
        audio_input=not is_text_only,
        audio_output=not is_text_only,
        text_output=True,
        close_on_disconnect=False,
        delete_room_on_close=False,
    )

    def _enqueue_transcript(speaker: str, text: str) -> None:
        if call_end_triggered:
            return
        try:
            _transcript_queue.put_nowait(
                lambda: livekit_services.add_transcript(
                    room_name=ctx.room.name,
                    speaker=speaker,
                    text=text,
                    assistant_id=assistant_id,
                    assistant_name=assistant.assistant_name,
                    to_number=to_number,
                    recording_path=recorder.s3_url,
                    created_by_email=assistant.assistant_created_by_email,
                    call_type=job_metadata.get("call_type"),
                    call_service=job_metadata.get("call_service") or job_metadata.get("service"),
                    platform_number=job_metadata.get("inbound_number"),
                )
            )
        except asyncio.QueueFull:
            logger.warning(f"Transcript queue full, dropping | room={room_name}")

    # --- Transcription Event Handler ---
    @session.on("conversation_item_added")
    def on_conversation_item(event):
        if not getattr(event.item, "text_content", None):
            return
        # Suppress all activity during hold
        if hold_controller.is_on_hold:
            if event.item.role == "assistant":
                session.interrupt()
            return
        # Block all activity until the call is ready
        if not gate.is_active:
            return
        # Sarvam parallel STT owns user transcripts when active
        if event.item.role == "user" and _use_sarvam_stt:
            return

        if filler_words_enabled and event.item.role in ("user", "assistant"):
            context_turns.append({"role": event.item.role, "text": event.item.text_content})

        if silence_watchdog and event.item.role == "user":
            silence_watchdog.on_user_message()

        if silence_watchdog and event.item.role == "assistant" and not user_is_speaking:
            silence_watchdog.on_assistant_message(event.item.text_content)

        _enqueue_transcript(event.item.role, event.item.text_content)

    # --- Start Session ---
    logger.info("Starting AgentSession...")
    await session.start(agent=agent_instance, room=ctx.room, room_options=room_options)
    logger.info("AgentSession started successfully")

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        nonlocal user_is_speaking
        is_speaking = event.new_state == "speaking"
        user_is_speaking = is_speaking

        if hold_controller.is_on_hold:
            return  # Suppress filler/silence during hold

        if silence_watchdog:
            silence_watchdog.on_user_state_changed(is_speaking)
        if filler_controller:
            if is_speaking:
                filler_controller.start()
            else:
                filler_controller.stop()

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        if hold_controller.is_on_hold and event.new_state == "speaking":
            session.interrupt()
        if silence_watchdog:
            if event.new_state == "speaking":
                silence_watchdog.on_agent_started_speaking()
            elif event.new_state == "listening":
                silence_watchdog.on_agent_done_speaking()
        if input_guard:
            if event.new_state == "speaking":
                input_guard.on_speaking_start()
            elif event.old_state == "speaking":
                input_guard.on_speaking_end()

    # --- Exotel Bridge: Call-Answered Handling ---
    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        if data.topic == "sip_bridge_events":
            try:
                msg = json.loads(data.data.decode())
                if msg.get("event") == "call_answered":
                    logger.info("Bridge reported call answered via data message (SIP 200 OK)")
                    gate.mark_answered()
                    if is_exotel_outbound:
                        asyncio.create_task(recorder.start_once())
                        asyncio.create_task(
                            livekit_services.update_call_status(
                                room_name=ctx.room.name,
                                call_status="answered",
                                call_status_reason=None,
                                answered_at=datetime.now(timezone.utc),
                            )
                        )
                elif msg.get("event") == "call_hold":
                    hold_controller.signal_hold(True)
                elif msg.get("event") == "call_resume":
                    hold_controller.signal_hold(False)
            except (json.JSONDecodeError, TypeError):
                pass

    # Wait for participant
    logger.info("Waiting for participant...")
    participant = await ctx.wait_for_participant()
    primary_participant_identity = participant.identity
    call_end_triggered = False

    # --- Max call-duration watchdog ---
    # Hard cap on active-call length. Counts from gate-ready (post-answer for Exotel outbound,
    # immediately otherwise). On expiry, agent says a brief farewell then teardown runs.
    _max_minutes = (
        getattr(interaction_config, "max_call_duration_minutes", None)
        or DEFAULT_MAX_CALL_DURATION_MINUTES
    )

    async def _max_duration_watchdog(limit_minutes: float):
        nonlocal _end_reason
        try:
            if not await gate.wait_until_ready(timeout=3600.0):
                return  # call never answered — nothing to police
            await asyncio.sleep(limit_minutes * 60.0)
            if call_end_triggered:
                return
            logger.warning(
                f"Max call duration reached ({limit_minutes:.2f}min) — ending gracefully | room={room_name}"
            )
            _end_reason = "max_duration_exceeded"
            try:
                farewell = "I'm sorry, our call has reached its time limit. Thank you for calling. Goodbye!"
                await session.generate_reply(
                    instructions=f"Say this exactly and nothing else: '{farewell}'",
                    allow_interruptions=False,
                )
            except Exception as e:
                logger.error(f"Failed to deliver max-duration farewell: {e}")
            await _flush_and_end_call(delay=3.0)
        except asyncio.CancelledError:
            pass

    _max_duration_task = asyncio.create_task(_max_duration_watchdog(_max_minutes))
    logger.info(f"Max-duration watchdog armed | limit={_max_minutes:.2f}min | room={room_name}")

    is_sip = participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
    is_exotel_bridge = False
    if participant.metadata:
        try:
            meta = json.loads(participant.metadata)
            is_exotel_bridge = meta.get("source") == "exotel_bridge"
        except (json.JSONDecodeError, TypeError):
            pass

    logger.info(
        f"Participant joined: {participant.identity} | "
        f"kind={participant.kind} | "
        f"is_sip={is_sip} | "
        f"is_exotel_bridge={is_exotel_bridge}"
    )

    # Background audio start
    if background_audio:
        try:
            asyncio.create_task(
                background_audio.start(room=ctx.room, agent_session=session)
            )
            logger.info("Background audio task spawned")
        except Exception as e:
            logger.error(f"Failed to start background audio: {e}")

    # Persistent Sarvam WS keepalive — holds connection open for entire call.
    if isinstance(tts, sarvam_plugin.TTS):
        asyncio.create_task(maintain_sarvam_connection(tts, _sarvam_stop))

    # Sarvam Saras v3 parallel STT — overrides user transcript when half-cascade + sarvam selected.
    if _use_sarvam_stt:
        def _on_sarvam_final(text: str) -> None:
            _enqueue_transcript("user", text)
            if silence_watchdog:
                silence_watchdog.on_user_message()

        asyncio.create_task(run_sarvam_parallel_stt(
            room=ctx.room,
            target_identity=primary_participant_identity,
            on_final=_on_sarvam_final,
            stop_event=_sarvam_stop,
        ))

    # --- Start Instruction ---
    should_speak_first = interaction_config.speaks_first
    if should_speak_first:
        start_instruction = agent_instance.start_instruction
        if start_instruction:
            allow_int = getattr(interaction_config, "allow_interruptions", False)
            _saved_td = None
            should_send_instruction = True
            try:
                # Disable server-side VAD before the Exotel gate wait, not just before generate_reply.
                # Pre-answer RTP audio (183, ring tone) during the 60s wait triggers the framework's
                # own generate_reply, which races with ours and logs spurious timeouts. Each call has
                # its own llm instance so this is safe under concurrency.
                if is_exotel_bridge and not allow_int and isinstance(llm, realtime.RealtimeModel):
                    _saved_td = llm._opts.turn_detection
                    llm.update_options(turn_detection=None)

                if is_exotel_bridge:
                    logger.info("Exotel bridge detected — waiting for call_answered event before speaking")
                    answered = await gate.wait_until_ready(timeout=60.0)
                    if answered:
                        recording_ready = await recorder.ensure_started(timeout=12.0)
                        if not recording_ready:
                            logger.warning(
                                "[EXOTEL] Recording did not become ready before first reply; proceeding"
                            )
                        logger.info("[EXOTEL] call_answered confirmed — sleeping 2s for RTP + egress warmup")
                        await asyncio.sleep(2.0)
                    else:
                        logger.warning("[EXOTEL] Timed out waiting for call_answered — skipping start instruction")
                        should_send_instruction = False

                if should_send_instruction:
                    # The text recorded for the silence watchdog (transcript when prerecorded).
                    spoken_text = start_instruction

                    # For non-Exotel, non-interruptible realtime models: disable VAD before speaking
                    # (Exotel already did it above). Applies to every greeting path below.
                    if not allow_int and not is_exotel_bridge and isinstance(llm, realtime.RealtimeModel):
                        if _saved_td is None:
                            _saved_td = llm._opts.turn_detection
                        llm.update_options(turn_detection=None)

                    # Prefer a prerecorded greeting when configured — skips LLM + TTS for both modes.
                    greeting_cfg = assistant.assistant_greeting_audio
                    played_prerecorded = False
                    if greeting_cfg.enabled and greeting_cfg.audio_id:
                        transcript = await play_prerecorded_greeting(session, greeting_cfg.audio_id, allow_int)
                        if transcript is not None:
                            played_prerecorded = True
                            spoken_text = transcript

                    if not played_prerecorded:
                        if is_realtime:
                            logger.info("Start instruction strategy | mode=realtime_speaks_first_via_user_input | provider = %s", realtime_provider)

                            if realtime_provider == "gemini":
                                from google.genai import types as genai_types

                                rt_session = agent_instance.realtime_llm_session
                                rt_session._send_client_event(
                                    genai_types.LiveClientRealtimeInput(text=start_instruction)
                                )
                            else:
                                # OpenAI realtime (audio out): standard greeting via generate_reply.
                                if not allow_int:
                                    agent_instance._allow_interruptions = False
                                try:
                                    await session.generate_reply(instructions=start_instruction, allow_interruptions=allow_int)
                                finally:
                                    agent_instance._allow_interruptions = NOT_GIVEN
                        else:
                            logger.info("Start instruction strategy | mode=pipeline_speaks_first_via_instructions")
                            try:
                                if not allow_int:
                                    agent_instance._allow_interruptions = False
                                await session.generate_reply(instructions=start_instruction, allow_interruptions=allow_int)
                            finally:
                                agent_instance._allow_interruptions = NOT_GIVEN

                    if silence_watchdog and spoken_text:
                        silence_watchdog.on_assistant_message(spoken_text)
                    logger.info("Start instruction sent successfully")
            except Exception as e:
                logger.error(f"Failed to send start instruction: {e}", exc_info=True)
            finally:
                if _saved_td is not None:
                    llm.update_options(turn_detection=_saved_td)
    else:
        logger.info(
            "assistant_speaks_first=False — skipping start instruction; "
            "assistant is silent and waiting for the user to speak first"
        )

    # --- Wait for Disconnect ---
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        nonlocal call_end_triggered
        if filler_controller:
            filler_controller.stop()
        if silence_watchdog:
            silence_watchdog.stop()
        logger.info(f"Participant disconnected: {participant.identity}")
        if participant.identity != primary_participant_identity:
            logger.info(
                f"Ignoring non-primary disconnect: {participant.identity} "
                f"(primary={primary_participant_identity})"
            )
            return
        if call_end_triggered:
            logger.info(f"Call end already triggered for room: {ctx.room.name}")
            return
        call_end_triggered = True  # Immediate guard before task creation
        asyncio.create_task(_flush_and_end_call(delay=0.0))  # No delay — user already gone
        logger.info(f"Agent session ended for room: {ctx.room.name}")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            ws_url=settings.LIVEKIT_URL,
            job_memory_warn_mb=1024,
            entrypoint_fnc=entrypoint,
            agent_name="api-agent",
            num_idle_processes=2,
            load_threshold=0.65,  # stop accepting new jobs at 65% CPU (default dev=inf)
        )
    )
