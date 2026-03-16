import asyncio
import logging
import random
from collections import deque
from typing import Final

from livekit.agents import AgentSession
from openai import AsyncOpenAI

from src.core.config import settings

REPROMPT_INTERVAL_SEC: Final[float] = 10.0
MAX_REPROMPTS: Final[int] = 2
_recent_fillers: deque[str] = deque(maxlen=5)
_client: AsyncOpenAI | None = None


async def generate_filler(context: list[dict[str, str]]) -> str | None:
    """Generate a short filler phrase for live backchanneling."""
    global _client
    if not settings.OPENAI_API_KEY:
        return None

    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    avoid = list(_recent_fillers)
    avoid_clause = f"Do not use any of these phrases: {avoid}. " if avoid else ""

    if context:
        context_lines = "\n".join(
            f"{index + 1}. [{turn['role'].capitalize()}]: {turn['text']}"
            for index, turn in enumerate(context[-4:])
        )
        context_block = f"Recent conversation:\n{context_lines}\n\n"
    else:
        context_block = ""

    try:
        response = await _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a human listener on a live voice call. The user is mid-sentence RIGHT NOW — "
                        "they haven't finished speaking.\n\n"
                        "Your ONLY job: produce a single backchannel filler (1–3 words) that a human would "
                        "murmur WHILE the other person is still talking — not after.\n\n"
                        "CRITICAL RULES:\n"
                        "- The filler must feel natural MID-SENTENCE, not as a response to a complete thought.\n"
                        "- Prefer ultra-short: 'Mm.', 'Yeah.', 'Mm-hmm.', 'Right.', 'Uh-huh.' for neutral flow.\n"
                        "- Tone-match only if the emotional signal is very strong:\n"
                        "    sad/heavy → 'Mm.', 'Yeah...', 'I see.'\n"
                        "    excited/surprising → 'Oh!', 'Wow.', 'Really?'\n"
                        "    thoughtful/explaining → 'Right.', 'Um-hmm.', 'Yeah.'\n"
                        "- NEVER complete their thought, answer, advise, or ask anything.\n"
                        "- NEVER use more than 3 words.\n"
                        "- No quotes. Natural punctuation only.\n"
                        "- Default to the shortest possible filler. When in doubt: 'Um-hmm.' or 'Yeah.'\n"
                        f"{avoid_clause}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{context_block}"
                        "The user is still speaking mid-sentence. "
                        "Output only the filler word or phrase a human listener would murmur right now."
                    ),
                },
            ],
            max_tokens=10,
            temperature=0.9,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            return None
        _recent_fillers.append(text)
        return text
    except Exception:
        return None


class SilenceWatchdogController:
    """Reprompt the user and end the session after repeated silence."""

    def __init__(
        self,
        session: AgentSession,
        logger: logging.Logger,
        reprompt_interval_sec: float = 10.0,
        max_reprompts: int = 2,
    ) -> None:
        self._session = session
        self._logger = logger
        self._reprompt_interval_sec = reprompt_interval_sec
        self._max_reprompts = max_reprompts
        self._silence_task: asyncio.Task | None = None
        self._reprompt_count = 0
        self._user_is_speaking = False
        self._skip_next_assistant_message = False


    def stop(self, reset_count: bool = True) -> None:
        """Stop silence tracking and optionally reset reprompt count."""
        if reset_count:
            self._reprompt_count = 0
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()
        self._silence_task = None

    def start(self) -> None:
        """Start silence tracking if not already running and user is silent."""
        if self._user_is_speaking:
            return
        if self._silence_task and not self._silence_task.done():
            return
        self._silence_task = asyncio.create_task(self._watchdog_loop())

    def on_user_message(self) -> None:
        """Reset silence tracking when the user replies."""
        self.stop(reset_count=True)

    def on_assistant_message(self, message_text: str) -> None:
        """Track assistant turns and start silence watchdog."""
        if not message_text:
            return

        if self._skip_next_assistant_message:
            self._skip_next_assistant_message = False
            return

        self.stop(reset_count=True)
        self.start()

    def on_user_state_changed(self, is_speaking: bool) -> None:
        """Pause or resume silence tracking based on user speaking state."""
        self._user_is_speaking = is_speaking
        if is_speaking:
            self.stop(reset_count=False) # Pause task, but keep count
            return
        self.start()

    async def _watchdog_loop(self) -> None:
        try:
            while True:
                if self._reprompt_count >= self._max_reprompts:
                    self._logger.info("[silence] ending session after repeated silence")
                    self.stop(reset_count=True)
                    self._session.shutdown()
                    return

                await asyncio.sleep(self._reprompt_interval_sec)

                if self._user_is_speaking:
                    return

                self._reprompt_count += 1
                self._logger.info(
                    "[silence] reprompt %s/%s",
                    self._reprompt_count,
                    self._max_reprompts,
                )
                self._skip_next_assistant_message = True
                await self._session.say(
                    "Sorry, I didn't catch that. Are you still there?",
                    allow_interruptions=True,
                )
                await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._logger.exception("[silence] watchdog failed")
        finally:
            if asyncio.current_task() is self._silence_task:
                self._silence_task = None


class FillerController:
    """Manage the filler word task lifecycle."""

    def __init__(
        self,
        session: AgentSession,
        context_turns: deque[dict[str, str]],
    ) -> None:
        self._session = session
        self._context_turns = context_turns
        self._filler_task: asyncio.Task | None = None

    def stop(self) -> None:
        """Stop the filler word task."""
        if self._filler_task and not self._filler_task.done():
            self._filler_task.cancel()
        self._filler_task = None

    def start(self) -> None:
        """Start the filler word loop."""
        self.stop()
        self._filler_task = asyncio.create_task(self._filler_loop())

    async def _filler_loop(self) -> None:
        """Generate and speak filler words periodically."""
        try:
            # Initial wait before first filler
            await asyncio.sleep(random.uniform(2.0, 3.0))
            while True:
                text = await generate_filler(list(self._context_turns))
                if text:
                    await self._session.say(text, allow_interruptions=True)
                await asyncio.sleep(random.uniform(5.0, 8.0))
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            if asyncio.current_task() is self._filler_task:
                self._filler_task = None
