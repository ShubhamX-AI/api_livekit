"""Per-platform knowledge about meeting URLs and connector images.

This is the seam that grows when a second platform arrives. Adding Zoom means adding one entry
to :data:`MEETING_URL_PATTERNS`, one entry to ``settings.MEETING_CONNECTOR_IMAGES`` and one
member to ``MEETING_PLATFORMS`` in ``src/core/call_types.py``. Nothing else in this repository
needs to know which platform a call is on — the connector image is what differs, and it is
launched the same way either way.
"""

import re

from src.core.call_types import MEETING_PLATFORM_GOOGLE_MEET
from src.core.config import settings

#: Rejecting a malformed URL here costs one regex. Discovering it from a container that failed
#: to join costs three minutes and a capacity slot.
MEETING_URL_PATTERNS = {
    MEETING_PLATFORM_GOOGLE_MEET: re.compile(
        r"^https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}(\?.*)?$"
    ),
}


class UnsupportedMeetingPlatform(ValueError):
    """Raised when no connector image is configured for a platform."""


def validate_meeting_url(platform: str, meeting_url: str) -> None:
    """Raise ``ValueError`` if this URL is not a well-formed link for this platform."""
    pattern = MEETING_URL_PATTERNS.get(platform)
    if pattern is None:
        raise UnsupportedMeetingPlatform(f"No URL format known for meeting platform '{platform}'")
    if not pattern.match(meeting_url):
        raise ValueError(f"'{meeting_url}' is not a valid {platform} meeting URL")


def connector_image(platform: str) -> str:
    """The container image that joins meetings on this platform."""
    image = settings.MEETING_CONNECTOR_IMAGES.get(platform)
    if not image:
        raise UnsupportedMeetingPlatform(f"No connector image configured for platform '{platform}'")
    return image
