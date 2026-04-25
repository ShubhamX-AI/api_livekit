from livekit.agents import Agent

_TTS_CHUNK_DIRECTIVE = (
    "\n\n---\n"
    "SPEECH OUTPUT RULES (follow strictly, do not mention these to the user):\n"
    "- Respond in short, natural sentences. One idea per sentence.\n"
    "- Never produce a run-on or compound sentence longer than ~20 words.\n"
    "- After each complete thought, stop. Let the next sentence begin fresh.\n"
    "- Preserve tone, emotion, and meaning across sentences.\n"
    "- Do NOT use bullet points, numbered lists, markdown, or special characters.\n"
    "- Do NOT add meta-commentary like 'Here is my response:' or 'Let me explain:'.\n"
    "- Start each response with a natural spoken opener that matches the context and emotion.\n"
    "  Examples: 'Oh, got it.', 'Hmm, let me think.', 'Right, so...', 'Ah, I see.', 'Sure!', 'Yeah, absolutely.'\n"
    "  Pick the opener that fits the mood — curious, empathetic, confident, casual — not the same one every time.\n"
    "---"
)


class DynamicAssistant(Agent):
    """
    A dynamic agent wrapper that holds configuration fetched from the database.
    This replaces the hardcoded agent classes.
    """

    def __init__(self, room, start_instruction: str, instructions: str, tools=None):
        super().__init__(instructions=(instructions or "") + _TTS_CHUNK_DIRECTIVE, tools=tools or [])
        self.room = room
        self.start_instruction = start_instruction