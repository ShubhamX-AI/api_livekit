import asyncio
import logging
from collections import deque
from typing import Final

from livekit.agents import AgentSession
from openai import AsyncOpenAI

from src.core.config import settings

REPROMPT_INTERVAL_SEC: Final[float] = 10.0
MAX_REPROMPTS: Final[int] = 2
_recent_fillers: deque[str] = deque(maxlen=5)


async def generate_filler(context: list[dict[str, str]]) -> str | None:
    """Generate a short filler phrase for live backchanneling."""
    if not settings.OPENAI_API_KEY:
        return None

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
        reprompt_interval_sec: float = REPROMPT_INTERVAL_SEC,
        max_reprompts: int = MAX_REPROMPTS,
    ) -> None:
        self._session = session
        self._logger = logger
        self._reprompt_interval_sec = reprompt_interval_sec
        self._max_reprompts = max_reprompts
        self._silence_task: asyncio.Task | None = None
        self._reprompt_count = 0
        self._waiting_for_user_response = False
        self._user_is_speaking = False
        self._skip_next_assistant_message = False

    def stop(self) -> None:
        """Stop silence tracking."""
        self._clear_waiting_state()

    def on_user_message(self) -> None:
        """Reset silence tracking when the user replies."""
        self._clear_waiting_state()

    def on_assistant_message(self, message_text: str) -> None:
        """Track assistant turns that expect a reply."""
        if not message_text:
            return

        if self._skip_next_assistant_message:
            self._skip_next_assistant_message = False
            return

        if self._assistant_expects_reply(message_text):
            self._waiting_for_user_response = True
            self._reprompt_count = 0
            self._cancel_watchdog_task()
            self._start_watchdog_task()
            return

        self._clear_waiting_state()

    def on_user_state_changed(self, is_speaking: bool) -> None:
        """Pause silence tracking while the user speaks."""
        self._user_is_speaking = is_speaking
        if is_speaking:
            self._cancel_watchdog_task()
            return
        self._start_watchdog_task()

    def _assistant_expects_reply(self, message_text: str) -> bool:
        normalized_text = " ".join(message_text.lower().split())
        if "?" in normalized_text:
            return True

        reply_phrases = (
            "let me know",
            "tell me",
            "please respond",
            "can you",
            "could you",
            "would you",
            "share with me",
        )
        return any(phrase in normalized_text for phrase in reply_phrases)

    def _clear_waiting_state(self) -> None:
        self._waiting_for_user_response = False
        self._reprompt_count = 0
        self._cancel_watchdog_task()

    def _cancel_watchdog_task(self) -> None:
        silence_task = self._silence_task
        if silence_task and not silence_task.done():
            silence_task.cancel()
        self._silence_task = None

    def _start_watchdog_task(self) -> None:
        if not self._waiting_for_user_response or self._user_is_speaking:
            return
        if self._silence_task and not self._silence_task.done():
            return
        self._silence_task = asyncio.create_task(self._watchdog_loop())

    async def _watchdog_loop(self) -> None:
        try:
            while self._waiting_for_user_response:
                if self._reprompt_count >= self._max_reprompts:
                    self._logger.info("[silence] ending session after repeated silence")
                    self._clear_waiting_state()
                    self._session.shutdown()
                    return

                await asyncio.sleep(self._reprompt_interval_sec)

                if not self._waiting_for_user_response or self._user_is_speaking:
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
