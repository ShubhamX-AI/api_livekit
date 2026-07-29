"""GET /tool/details hides webhook secrets, and the mask cannot be written back."""

import unittest

from pydantic import ValidationError

from src.api.models.api_schemas import CreateTool, UpdateTool
from src.core.providers.keys import mask_secret_values

WEBHOOK_CONFIG = {
    "url": "https://api.example.com/weather",
    "timeout": 5,
    "api_key": "sk_real",
    "headers": {"Authorization": "Bearer real-token", "Accept": "application/json"},
}


class TestToolConfigMasking(unittest.TestCase):
    def test_details_masking_hides_only_secrets(self):
        masked = mask_secret_values(WEBHOOK_CONFIG)
        self.assertEqual(masked["headers"]["Authorization"], "****")
        self.assertEqual(masked["headers"]["Accept"], "application/json")
        self.assertEqual(masked["api_key"], "****")
        self.assertEqual(masked["url"], WEBHOOK_CONFIG["url"])
        self.assertEqual(masked["timeout"], 5)

    def test_empty_config_passthrough(self):
        self.assertIsNone(mask_secret_values(None))

    def test_masked_config_cannot_be_written_back(self):
        """Storing the mask would leave the webhook calling with a literal '****'."""
        masked = mask_secret_values(WEBHOOK_CONFIG)
        with self.assertRaises(ValidationError):
            UpdateTool(tool_execution_config=masked)
        with self.assertRaises(ValidationError):
            CreateTool(
                tool_name="lookup_weather",
                tool_description="Look up weather",
                tool_execution_type="webhook",
                tool_execution_config=masked,
            )

    def test_real_config_accepted(self):
        request = UpdateTool(tool_execution_config=WEBHOOK_CONFIG)
        self.assertEqual(
            request.tool_execution_config["headers"]["Authorization"], "Bearer real-token"
        )


if __name__ == "__main__":
    unittest.main()
