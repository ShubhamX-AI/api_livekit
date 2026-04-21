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
from livekit.plugins.openai import realtime
from livekit.plugins.google import realtime as google_realtime
from openai.types.realtime import AudioTranscription
import os
import asyncio
import json
from datetime import datetime, timezone

from src.core.config import settings
from src.core.logger import logger, setup_logging
from src.core.agents.dynamic_assistant import DynamicAssistant
from src.core.agents.inbound_context import resolve_inbound_context
from src.core.agents.session_lifecycle import CallReadinessGate, RecordingManager
from src.core.agents.tts_factory import create_tts
from src.core.agents.utils import render_prompt
from src.core.agents.voice_features import SilenceWatchdogController, FillerController, HoldController
from src.core.agents.tool_builder import build_tools_from_db
from src.core.db.database import Database
from src.core.db.db_schemas import Assistant, InboundContextStrategy, UsageRecord, CallRecord
from src.services.livekit.livekit_svc import LiveKitService
from livekit.agents.metrics import UsageCollector


setup_logging()
load_dotenv(override=True)


# Helper to build background audio player based on interaction config
def build_background_audio(interaction_config) -> BackgroundAudioPlayer | None:
    ambient_sound = None
    if getattr(interaction_config, "background_sound_enabled", True):
        ambient_path = os.path.join(settings.AUDIO_DIR, "office-ambience_48k.wav")
        ambient_sound = AudioConfig(ambient_path, volume=0.4)

    thinking_sound = None
    if getattr(interaction_config, "thinking_sound_enabled", True):
        typing_path = os.path.join(settings.AUDIO_DIR, "typing-sound_48k.wav")
        thinking_sound = AudioConfig(typing_path, volume=0.5)

    if ambient_sound is None and thinking_sound is None:
        return None

    return BackgroundAudioPlayer(
        ambient_sound=ambient_sound,
        thinking_sound=thinking_sound,
    )


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
    # Filler words require external TTS (session.say), disabled in realtime mode
    filler_words_enabled = bool(interaction_config.filler_words) and not is_realtime
    silence_reprompts_enabled = bool(interaction_config.silence_reprompts)
    background_sound_enabled = bool(getattr(interaction_config, "background_sound_enabled", True))
    thinking_sound_enabled = bool(getattr(interaction_config, "thinking_sound_enabled", True))
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

    # Start recording immediately for non-Exotel calls
    if not is_exotel_outbound:
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

            # Determine realtime provider from config
            llm_realtime_provider = None
            if is_realtime:
                llm_realtime_provider = (assistant.assistant_llm_config or {}).get("provider")

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

    # Single teardown path used by both EndCallTool and participant disconnect
    async def _flush_and_end_call(delay: float = 0.0):
        nonlocal call_end_triggered
        call_end_triggered = True  # Block duplicate from disconnect handler
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
        await livekit_services.end_call(room_name=ctx.room.name, assistant_id=assistant_id)
        await livekit_services.delete_room(room_name=ctx.room.name)

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

    # Provider selection for realtime mode
    realtime_provider: str | None = None

    if is_realtime:
        # Full realtime mode: single model handles STT + LLM + TTS
        llm_config = assistant.assistant_llm_config or {}
        realtime_provider = llm_config.get("provider", "gemini")

        if realtime_provider == "gemini":
            llm = google_realtime.RealtimeModel(
                model=llm_config.get("model", "gemini-3.1-flash-live-preview"),
                voice=llm_config.get("voice", "Puck"),
                modalities=["AUDIO"],
                instructions=assistant.assistant_prompt,
                api_key=llm_config.get("api_key") or settings.GOOGLE_API_KEY,
            )
        else:
            logger.error(f"Unsupported realtime provider: {realtime_provider}")
            return

        logger.info(f"Realtime mode | provider={realtime_provider} | model={llm_config.get('model')}")
    else:
        # Half-cascade mode: OpenAI Realtime for STT+LLM, separate TTS for audio
        llm = realtime.RealtimeModel(
            model="gpt-realtime",
            input_audio_transcription=AudioTranscription(
                model="gpt-4o-transcribe",
                prompt=(
                    "The speaker is multilingual and switches between different languages dynamically. "
                    "Transcribe exactly what is spoken without translating."
                ),
            ),
            input_audio_noise_reduction="near_field",
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="medium",
                create_response=True,
                interrupt_response=False,  # Don't interrupt LLM response mid-generation; let it finish and handle turn-taking in the agent logic instead
            ),
            modalities=["text"],
            api_key=settings.OPENAI_API_KEY,
        )
        logger.info("Half-cascade mode | llm=openai | tts=%s", assistant.assistant_tts_model)

    # --- Build TTS (only for pipeline mode) ---
    tts = None
    if not is_realtime:
        tts = create_tts(assistant)
        if tts is None:
            return

    # --- Session Setup ---
    if is_realtime:
        session = AgentSession(llm=llm)
    else:
        session = AgentSession(
            llm=llm,
            tts=tts,
            preemptive_generation=True,
            use_tts_aligned_transcript=True,
            aec_warmup_duration=0.8,  # seconds
            turn_handling=TurnHandlingOptions(
                turn_detection="realtime_llm",
                endpointing={
                    "mode": "dynamic",
                    "min_delay": 0.1,
                    "max_delay": 3.0,
                },
                interruption={
                    "mode": "adaptive",
                    "min_duration": 0.8,
                    "min_words": 2,
                    "discard_audio_if_uninterruptible": True,
                    "false_interruption_timeout": 2.0,
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

    # Background audio
    background_audio = build_background_audio(interaction_config)

    # Text input only for web calls
    is_web_call = job_metadata.get("call_type") == "web"
    logger.info(f"Session input mode | call_type={job_metadata.get('call_type')} | text_input={is_web_call}")

    room_options = room_io.RoomOptions(
        text_input=is_web_call,
        audio_input=True,
        audio_output=True,
        close_on_disconnect=False,
        delete_room_on_close=False,
    )

    # --- Transcription Event Handler ---
    @session.on("conversation_item_added")
    def on_conversation_item(event):
        if not event.item.text_content:
            return
        # Suppress all activity during hold
        if hold_controller.is_on_hold:
            if event.item.role == "assistant":
                session.interrupt()
            return
        # Block all activity until the call is ready
        if not gate.is_active:
            return

        if filler_words_enabled and event.item.role in ("user", "assistant"):
            context_turns.append({"role": event.item.role, "text": event.item.text_content})

        if silence_watchdog and event.item.role == "user":
            silence_watchdog.on_user_message()

        if silence_watchdog and event.item.role == "assistant" and not user_is_speaking:
            silence_watchdog.on_assistant_message(event.item.text_content)

        if call_end_triggered:
            return
        try:
            _transcript_queue.put_nowait(
                lambda: livekit_services.add_transcript(
                    room_name=ctx.room.name,
                    speaker=event.item.role,
                    text=event.item.text_content,
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

    # --- Start Instruction ---
    should_speak_first = interaction_config.speaks_first
    if should_speak_first:
        start_instruction = agent_instance.start_instruction
        if start_instruction:
            try:
                if is_exotel_bridge:
                    logger.info("Exotel bridge detected — waiting for call_answered event before speaking")
                    answered = await gate.wait_until_ready(timeout=60.0)
                    if answered:
                        recording_ready = await recorder.ensure_started(timeout=8.0)
                        if not recording_ready:
                            logger.warning(
                                "[EXOTEL] Recording did not become ready before first reply; proceeding"
                            )
                        logger.info("[EXOTEL] call_answered confirmed — sleeping 0.5s for RTP stabilization")
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("[EXOTEL] Timed out waiting for call_answered — skipping start instruction")

                if gate.is_active:
                    if is_realtime:
                        logger.info("Start instruction strategy | mode=realtime_speaks_first_via_user_input | provider = %s", realtime_provider)

                        if realtime_provider == "gemini":
                            from google.genai import types as genai_types

                            rt_session = agent_instance.realtime_llm_session
                            rt_session._send_client_event(
                                genai_types.LiveClientRealtimeInput(text=start_instruction)
                            )
                        else:
                            logger.error("Realtime provider not supported")
                    else:
                        logger.info("Start instruction strategy | mode=pipeline_speaks_first_via_instructions")
                        # RealtimeModel with capabilities.turn_detection=True silently resets
                        # allow_interruptions=False to NOT_GIVEN in _generate_reply. The SpeechHandle
                        # then falls back to activity.allow_interruptions → _agent._allow_interruptions.
                        # Setting it here ensures the first message's SpeechHandle is truly uninterruptible.
                        # NOTE: _allow_interruptions is a private library attr — verify on livekit-agents upgrades.
                        allow_int = getattr(interaction_config, "allow_interruptions", False)
                        if not allow_int:
                            agent_instance._allow_interruptions = False
                        try:
                            await session.generate_reply(instructions=start_instruction, allow_interruptions=allow_int)
                        finally:
                            agent_instance._allow_interruptions = NOT_GIVEN
                    if silence_watchdog:
                        silence_watchdog.on_assistant_message(start_instruction)
                    logger.info("Start instruction sent successfully")
            except Exception as e:
                logger.error(f"Failed to send start instruction: {e}", exc_info=True)
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
