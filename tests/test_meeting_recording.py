"""When each call type starts its recording.

A meeting call used to start egress at job pickup, so the 30-40s the connector's browser spends
launching and waiting for admission landed at the head of every S3 object.
"""

import unittest

from src.core.agents.session_lifecycle import should_record_on_join


class ShouldRecordOnJoinTests(unittest.TestCase):
    def test_meeting_call_waits_for_the_connector(self):
        self.assertFalse(
            should_record_on_join(
                is_exotel_outbound=False, is_text_only=False, is_meeting_call=True
            )
        )

    def test_web_call_records_immediately(self):
        self.assertTrue(
            should_record_on_join(
                is_exotel_outbound=False, is_text_only=False, is_meeting_call=False
            )
        )

    def test_text_only_chat_has_no_audio_to_record(self):
        self.assertFalse(
            should_record_on_join(
                is_exotel_outbound=False, is_text_only=True, is_meeting_call=False
            )
        )

    def test_exotel_outbound_waits_for_call_answered(self):
        self.assertFalse(
            should_record_on_join(
                is_exotel_outbound=True, is_text_only=False, is_meeting_call=False
            )
        )


if __name__ == "__main__":
    unittest.main()
