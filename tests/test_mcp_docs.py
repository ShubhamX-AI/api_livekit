import json
import unittest

import httpx
from starlette.applications import Starlette
from starlette.routing import Route

from src.api.mcp_docs import _load_index, asgi_app, get_doc, list_docs, mcp, search_docs


class TestMcpDocs(unittest.TestCase):
    def test_index_covers_docs(self):
        index = _load_index()
        self.assertGreater(len(index), 50)
        title, text = index["api/calls/trigger.md"]
        self.assertTrue(title)
        self.assertIn("#", text)

    def test_get_doc_accepts_path_with_and_without_suffix(self):
        with_suffix = get_doc("api/calls/trigger.md")
        without_suffix = get_doc("api/calls/trigger")
        self.assertEqual(with_suffix, without_suffix)
        self.assertIn("api/calls/trigger.md", with_suffix)

    def test_get_doc_rejects_traversal(self):
        for bad in (
            "../pyproject.toml",
            "api/../../pyproject.toml",
            "../../etc/passwd",
        ):
            self.assertIn("outside documentation tree", get_doc(bad))

    def test_get_doc_leading_slash_stays_inside_docs(self):
        # "/etc/passwd" is treated as docs/etc/passwd.md, i.e. simply missing.
        self.assertIn("No page at", get_doc("/etc/passwd"))
        self.assertEqual(
            get_doc("/api/calls/trigger.md"), get_doc("api/calls/trigger.md")
        )

    def test_get_doc_unknown_page(self):
        self.assertIn("No page at", get_doc("api/nope/missing.md"))

    def test_search_ranks_the_page_that_answers_the_question(self):
        """The right page must be in the top three for the questions agents actually ask.

        The old score was a raw substring count, so a long page that repeated "call" beat the
        short page about queue status, and every new docs page could push answers further
        down. These are a sample of the 26 questions the BM25 constants were tuned on.
        """
        cases = {
            "outbound call queue status": "api/calls/queue-status.md",
            "create assistant cascade": "api/assistant/create.md",
            "end call webhook payload": "api/calls/webhook.md",
            "tool attach": "api/tools/attach.md",
            "upload greeting audio": "api/audio/upload.md",
            "duplex gpt-live how it works": "architecture/duplex-mode.md",
            "elevenlabs price": "reference/pricing.md",
            "api key authentication": "api/authentication.md",
            "release dates": "changelog.md",
            "trigger outbound call": "api/calls/trigger.md",
        }
        for query, page in cases.items():
            with self.subTest(query=query):
                result = search_docs(query, limit=3)
                self.assertIn(f"path: {page} ", result)

    def test_search_finds_plural_and_singular_forms(self):
        self.assertIn("path: api/tools/attach.md ", search_docs("attach tools", limit=3))

    def test_the_changelog_is_reachable(self):
        """The server's instructions point agents at changelog.md, so get_doc must serve it."""
        self.assertIn("# Changelog", get_doc("changelog.md"))
        self.assertIn("changelog.md", list_docs())

    def test_search_empty_and_miss(self):
        self.assertIn("Empty query", search_docs("   "))
        self.assertIn("No pages match", search_docs("zzzzqqqnotaword"))

    def test_list_docs_lists_sections(self):
        result = list_docs()
        self.assertIn("## api", result)
        self.assertIn("api/calls/trigger.md", result)



class TestMcpOverHttp(unittest.IsolatedAsyncioTestCase):
    """The tools through the real streamable-HTTP handler mounted at /mcp, not just as functions."""

    async def _call(self, client, method, params=None, id_=1):
        response = await client.post(
            "/mcp",
            headers={"accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.text
        if "data:" in body:
            body = [line[5:] for line in body.splitlines() if line.startswith("data:")][-1]
        return json.loads(body)["result"]

    async def test_initialize_list_and_call(self):
        app = Starlette(routes=[Route("/mcp", endpoint=asgi_app)])
        async with mcp.session_manager.run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                init = await self._call(
                    client,
                    "initialize",
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                )
                self.assertEqual(init["serverInfo"]["name"], "livekit-api-docs")

                tools = await self._call(client, "tools/list", id_=2)
                self.assertEqual(
                    {tool["name"] for tool in tools["tools"]},
                    {"list_docs", "get_doc", "search_docs"},
                )

                found = await self._call(
                    client,
                    "tools/call",
                    {"name": "search_docs", "arguments": {"query": "queue status", "limit": 3}},
                    id_=3,
                )
                self.assertIn("api/calls/queue-status.md", found["content"][0]["text"])

                page = await self._call(
                    client,
                    "tools/call",
                    {"name": "get_doc", "arguments": {"path": "../pyproject.toml"}},
                    id_=4,
                )
                self.assertIn("outside documentation tree", page["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
