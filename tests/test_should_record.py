import unittest

from src.core.agents.session import should_record


class TestShouldRecord(unittest.TestCase):
    """Decides which conversation items reach the stored transcript.

    The regression this pins: `gate_active` flips on one `call_answered` SIP packet, and
    user speech used to be gated on it — so a single dropped packet silently emptied the
    whole call's transcript while the conversation carried on normally.
    """

    def test_caller_is_recorded_before_the_call_is_marked_answered(self):
        self.assertTrue(should_record("user", on_hold=False, gate_active=False))

    def test_caller_is_recorded_during_hold(self):
        self.assertTrue(should_record("user", on_hold=True, gate_active=True))

    def test_agent_is_not_recorded_before_the_call_is_answered(self):
        self.assertFalse(should_record("assistant", on_hold=False, gate_active=False))

    def test_agent_is_not_recorded_during_hold(self):
        self.assertFalse(should_record("assistant", on_hold=True, gate_active=True))

    def test_agent_is_recorded_on_a_live_call(self):
        self.assertTrue(should_record("assistant", on_hold=False, gate_active=True))

    def test_unknown_roles_follow_the_agent_rule(self):
        # Anything that is not the caller is treated as agent-side output.
        self.assertFalse(should_record(None, on_hold=True, gate_active=True))
        self.assertTrue(should_record("system", on_hold=False, gate_active=True))


if __name__ == "__main__":
    unittest.main()
