import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from src.api.routes.admin import admin_calls_by_phone_number
from src.api.routes.analytics import get_calls_by_phone_number


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self):
        return self._rows


class TestPhoneNumberPlatformGrouping(unittest.IsolatedAsyncioTestCase):
    async def test_analytics_groups_by_platform_bucket_and_keeps_avg(self):
        captured = {}
        start_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 3, 31, tzinfo=timezone.utc)

        def fake_aggregate(pipeline):
            captured["pipeline"] = pipeline
            return _FakeCursor(
                [
                    {
                        "phone_number": "WEB_CALL",
                        "total_calls": 2,
                        "total_duration_minutes": 10.0,
                        "total_duration_hours": 0.17,
                        "avg_duration_minutes": 5.0,
                    }
                ]
            )

        with patch("src.api.routes.analytics.CallRecord.aggregate", side_effect=fake_aggregate):
            response = await get_calls_by_phone_number(
                start_date=start_date,
                end_date=end_date,
                assistant_id="assistant-1",
                current_user=SimpleNamespace(user_email="user@example.com"),
            )

        self.assertEqual(response.data["phone_numbers"][0]["phone_number"], "WEB_CALL")
        pipeline = captured["pipeline"]
        self.assertEqual(pipeline[0]["$match"]["created_by_email"], "user@example.com")
        self.assertEqual(pipeline[0]["$match"]["assistant_id"], "assistant-1")
        self.assertEqual(pipeline[0]["$match"]["started_at"]["$gte"], start_date)
        self.assertEqual(pipeline[0]["$match"]["started_at"]["$lte"], end_date)
        self.assertEqual(
            pipeline[1]["$group"]["_id"],
            {
                "$cond": [
                    {"$or": [{"$eq": ["$call_type", "web"]}, {"$eq": ["$call_service", "web"]}]},
                    "WEB_CALL",
                    {"$ifNull": ["$platform_number", "UNKNOWN_PLATFORM"]},
                ]
            },
        )
        self.assertEqual(pipeline[2], {"$sort": {"total_duration_minutes": -1}})
        self.assertIn("avg_duration_minutes", pipeline[3]["$project"])

    async def test_admin_groups_by_platform_bucket(self):
        captured = {}
        start_date = datetime(2026, 3, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 3, 31, tzinfo=timezone.utc)

        def fake_aggregate(pipeline):
            captured["pipeline"] = pipeline
            return _FakeCursor(
                [
                    {
                        "phone_number": "UNKNOWN_PLATFORM",
                        "total_calls": 3,
                        "total_duration_minutes": 12.5,
                        "total_duration_hours": 0.21,
                    }
                ]
            )

        with patch("src.api.routes.admin.CallRecord.aggregate", side_effect=fake_aggregate):
            response = await admin_calls_by_phone_number(
                start_date=start_date,
                end_date=end_date,
                user_email="alice@example.com",
                current_user=SimpleNamespace(user_email="super-admin@example.com"),
            )

        self.assertEqual(response.data["phone_numbers"][0]["phone_number"], "UNKNOWN_PLATFORM")
        pipeline = captured["pipeline"]
        self.assertEqual(pipeline[0]["$match"]["created_by_email"], "alice@example.com")
        self.assertEqual(pipeline[0]["$match"]["started_at"]["$gte"], start_date)
        self.assertEqual(pipeline[0]["$match"]["started_at"]["$lte"], end_date)
        self.assertEqual(
            pipeline[1]["$group"]["_id"],
            {
                "$cond": [
                    {"$or": [{"$eq": ["$call_type", "web"]}, {"$eq": ["$call_service", "web"]}]},
                    "WEB_CALL",
                    {"$ifNull": ["$platform_number", "UNKNOWN_PLATFORM"]},
                ]
            },
        )
        self.assertEqual(pipeline[2], {"$sort": {"total_duration_minutes": -1}})
        self.assertNotIn("avg_duration_minutes", pipeline[3]["$project"])


if __name__ == "__main__":
    unittest.main()
