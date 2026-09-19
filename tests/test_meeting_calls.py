"""Tests for the meeting-call vocabulary and the connector's platform seam.

Two things are worth pinning down here. First, that a meeting call is not mistaken for a phone
call — the mis-classification is silent, and its only symptom is narrowband tuning applied to
wideband meeting audio, which degrades transcription rather than breaking it. Second, that a
malformed meeting URL is rejected before anything is reserved or launched.
"""

import unittest

from src.core.call_types import (
    CALL_TYPE_INBOUND,
    CALL_TYPE_MEETING,
    CALL_TYPE_OUTBOUND,
    CALL_TYPE_WEB,
    MEETING_PLATFORM_GOOGLE_MEET,
    is_phone_call,
)
from src.core.config import settings
from src.services.meeting_connector import platforms


class TestPhoneCallClassification(unittest.TestCase):
    def test_telephony_call_types_are_phone_calls(self):
        self.assertTrue(is_phone_call(CALL_TYPE_OUTBOUND))
        self.assertTrue(is_phone_call(CALL_TYPE_INBOUND))

    def test_web_and_meeting_calls_are_not_phone_calls(self):
        self.assertFalse(is_phone_call(CALL_TYPE_WEB))
        self.assertFalse(is_phone_call(CALL_TYPE_MEETING))

    def test_missing_call_type_is_treated_as_telephony(self):
        """Rows written before call_type existed carry None. Narrowband tuning on wideband
        audio is a worse outcome than the reverse, so this direction is deliberate."""
        self.assertTrue(is_phone_call(None))


class TestMeetingUrlValidation(unittest.TestCase):
    def test_accepts_a_real_google_meet_url(self):
        platforms.validate_meeting_url(MEETING_PLATFORM_GOOGLE_MEET, "https://meet.google.com/abc-defg-hij")

    def test_accepts_a_query_string(self):
        platforms.validate_meeting_url(
            MEETING_PLATFORM_GOOGLE_MEET, "https://meet.google.com/abc-defg-hij?authuser=0"
        )

    def test_rejects_wrong_host_and_wrong_code_shape(self):
        for bad in (
            "https://zoom.us/j/1234567890",
            "https://meet.google.com/abcdefghij",
            "http://meet.google.com/abc-defg-hij",
            "https://meet.google.com/",
        ):
            with self.assertRaises(ValueError, msg=bad):
                platforms.validate_meeting_url(MEETING_PLATFORM_GOOGLE_MEET, bad)

    def test_unknown_platform_is_rejected_rather_than_allowed(self):
        with self.assertRaises(platforms.UnsupportedMeetingPlatform):
            platforms.validate_meeting_url("zoom", "https://zoom.us/j/1234567890")


class TestConnectorTimeoutContract(unittest.TestCase):
    """Pin the cross-repository deadline contract.

    The connector service gives a human 300 seconds to admit the bot from the Google Meet
    waiting room (its WAITING_ROOM_TIMEOUT_SECONDS). If this side's readiness deadline is
    shorter, it expires first, marks the call failed and deletes the LiveKit room out from
    under a connector that is still working — which is exactly the bug these two settings
    were split to fix. Nothing else in either repository records that coupling, so it is
    recorded here.
    """

    CONNECTOR_WAITING_ROOM_TIMEOUT_SECONDS = 300

    def test_readiness_deadline_outlasts_the_connector_waiting_room(self):
        self.assertGreaterEqual(
            settings.MEETING_CONNECTOR_READY_TIMEOUT_SECONDS,
            self.CONNECTOR_WAITING_ROOM_TIMEOUT_SECONDS + 60,
        )

    def test_join_deadline_is_the_shorter_of_the_two(self):
        # A connector that never joins the room at all is a dispatch or capacity failure,
        # not a slow human, so it must still fail fast.
        self.assertLess(
            settings.MEETING_CONNECTOR_JOIN_TIMEOUT_SECONDS,
            settings.MEETING_CONNECTOR_READY_TIMEOUT_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
