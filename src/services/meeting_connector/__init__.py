"""Meeting-platform URL validation shared by meeting-call routes."""

from .platforms import UnsupportedMeetingPlatform, validate_meeting_url

__all__ = [
    "UnsupportedMeetingPlatform",
    "validate_meeting_url",
]
