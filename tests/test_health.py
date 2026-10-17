import asyncio
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import health
from src.core.config import settings
from src.core.version import __version__


async def _ok():
    return None


async def _refused():
    raise ConnectionRefusedError("[Errno 111] Connection refused")


async def _hangs():
    await asyncio.sleep(60)


class TestHealth(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(health.router)
        self.client = TestClient(app)

    def _get(self, db, lk):
        with (
            patch.object(health, "ping_db", lambda: db()),
            patch.object(health.LiveKitService, "ping", lambda self: lk()),
        ):
            return self.client.get("/health")  # no Authorization header on purpose

    def test_all_up(self):
        r = self._get(_ok, _ok)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        data = body["data"]
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["version"], __version__)
        self.assertEqual(set(data["checks"]), {"mongodb", "livekit"})
        self.assertTrue(all(c["ok"] and "error" not in c for c in data["checks"].values()))

    def test_datastore_down_degrades_but_returns_200(self):
        r = self._get(_refused, _ok)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["success"])
        data = body["data"]
        self.assertEqual(data["status"], "degraded")
        self.assertIn("ConnectionRefusedError", data["checks"]["mongodb"]["error"])
        self.assertTrue(data["checks"]["livekit"]["ok"])

    def test_hung_probe_is_cut_off_by_the_health_timeout(self):
        with patch.object(settings, "HEALTH_PROBE_TIMEOUT_S", 0.05):
            r = self._get(_ok, _hangs)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["checks"]["livekit"]["error"], "TimeoutError")

    def test_default_timeout_is_short(self):
        self.assertLessEqual(settings.HEALTH_PROBE_TIMEOUT_S, 5)


if __name__ == "__main__":
    unittest.main()
