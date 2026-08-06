import unittest

from src.core.agents.utils import render_prompt

# Mirrors the render_data assembly in src/core/agents/session.py (~lines 220-255):
# call metadata spread flat plus a `call.*` alias, then the inbound webhook response
# spread flat on top. Kept as a copy because the real merge is inline in entrypoint(),
# which needs a live JobContext, LiveKit, and Mongo to reach. Update both together.
JOB_METADATA = {
    "call_type": "inbound",
    "caller_number": "+919876543210",
    "inbound_number": "918044319240",
}


def _render_data(context_data):
    return {**JOB_METADATA, "call": JOB_METADATA, **context_data}


class TestInboundWebhookContext(unittest.TestCase):
    """The webhook response is spread as-is: its shape is the placeholder path."""

    def test_flat_response_resolves_a_bare_placeholder(self):
        # The case that was impossible before: no forced `context.` prefix.
        data = _render_data({"name": "John"})
        self.assertEqual(render_prompt("Hello {{name}}", data), "Hello John")

    def test_legacy_context_wrapper_still_resolves(self):
        # "context" is now an ordinary key, so existing prompts keep working.
        data = _render_data({"context": {"name": "John"}})
        self.assertEqual(render_prompt("Hello {{context.name}}", data), "Hello John")

    def test_webhook_key_shadows_call_metadata_but_not_the_call_alias(self):
        data = _render_data({"caller_number": "+911111111111"})
        self.assertEqual(render_prompt("{{caller_number}}", data), "+911111111111")
        self.assertEqual(render_prompt("{{call.caller_number}}", data), "+919876543210")


if __name__ == "__main__":
    unittest.main()
