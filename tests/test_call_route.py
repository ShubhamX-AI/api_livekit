import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from src.api.models.api_schemas import TriggerOutboundCall
from src.api.routes.call import trigger_outbound_call


class QueryField:
    def __eq__(self, other):
        return other


class TestCallRoute(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_trunk_service_mismatch(self):
        request = TriggerOutboundCall(
            assistant_id="assistant-1",
            trunk_id="trunk-1",
            to_number="+911234567890",
            call_service="exotel",
            metadata=None,
        )
        current_user = SimpleNamespace(user_email="user@example.com")
        assistant = SimpleNamespace(assistant_id="assistant-1", assistant_name="Assistant")
        twilio_trunk = SimpleNamespace(trunk_type="twilio", trunk_config={})

        assistant_model = SimpleNamespace(
            assistant_id=QueryField(),
            assistant_created_by_email=QueryField(),
            find_one=AsyncMock(return_value=assistant),
        )
        trunk_model = SimpleNamespace(
            trunk_id=QueryField(),
            trunk_created_by_email=QueryField(),
            trunk_is_active=QueryField(),
            find_one=AsyncMock(return_value=twilio_trunk),
        )

        with patch("src.api.routes.call.Assistant", assistant_model), patch(
            "src.api.routes.call.OutboundSIP", trunk_model
        ):
            with self.assertRaises(HTTPException) as ctx:
                await trigger_outbound_call(request=request, current_user=current_user)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("does not match", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
