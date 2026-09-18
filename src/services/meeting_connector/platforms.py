"""Per-platform knowledge about meeting URLs.

This is the seam that grows when a second platform arrives. Adding Zoom means adding one entry
to :data:`MEETING_URL_PATTERNS` and one member to ``MEETING_PLATFORMS`` in
``src/core/call_types.py``.
"""

import re

from src.core.call_types import MEETING_PLATFORM_GOOGLE_MEET

#: Rejecting a malformed URL here costs one regex. Discovering it from a container that failed
#: to join costs three minutes and a capacity slot.
MEETING_URL_PATTERNS = {
    MEETING_PLATFORM_GOOGLE_MEET: re.compile(
        r"^https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}(\?.*)?$"
    ),
}


class UnsupportedMeetingPlatform(ValueError):
    """Raised when no URL format is configured for a platform."""


def validate_meeting_url(platform: str, meeting_url: str) -> None:
    """Raise ``ValueError`` if this URL is not a well-formed link for this platform."""
    pattern = MEETING_URL_PATTERNS.get(platform)
    if pattern is None:
        raise UnsupportedMeetingPlatform(f"No URL format known for meeting platform '{platform}'")
    if not pattern.match(meeting_url):
        raise ValueError(f"'{meeting_url}' is not a valid {platform} meeting URL")
