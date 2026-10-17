"""MCP server exposing this project's MkDocs documentation to AI agents.

The same markdown under ``docs/`` that MkDocs renders into the static site at
``/documentation`` is served here as agent-callable tools over streamable HTTP
at ``/mcp``. Raw markdown, not the built HTML — that is what an LLM wants.

Three tools: ``list_docs`` (table of contents), ``get_doc`` (one page verbatim),
``search_docs`` (BM25 keyword ranking across every page).
"""

import math
import re
from collections import Counter
from pathlib import Path

from mcp.server import MCPServer

from src.core.logger import logger
from src.core.version import __version__

DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

MAX_SNIPPET_CHARS = 300
# Ranking constants, tuned on 26 real questions (agent-tracking/plan/08-…): the right page is
# first for 22 and in the top three for 25, against 18 in the top three for the raw word count
# this replaced. TITLE_BOOST: a query word in the page's title or path adds this many times the
# word's rarity — the title names what the page is about, the body only mentions things.
# K1 caps how much repeating a word helps; B discounts long pages, which is what stops a page
# that mentions everything from outranking the short page that is about the question.
TITLE_BOOST = 2.0
BM25_K1 = 1.2
BM25_B = 0.5

# ponytail: index built once on first tool call, never invalidated — docs are
# baked into the Docker image and immutable for the life of the process.
_index: dict[str, tuple[str, str]] | None = None
_terms: dict[str, tuple[Counter, int, set[str]]] | None = None


def _title_of(text: str, relpath: str) -> str:
    """First markdown H1 in the page, falling back to its path."""
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return relpath


def _words(text: str) -> list[str]:
    """Lowercase whole words with a trailing plural `s` folded, so "calls" matches "call"."""
    return [
        w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
        for w in re.findall(r"[a-z0-9]+", text.lower())
    ]


def _load_index() -> dict[str, tuple[str, str]]:
    """Map of ``relative/path.md`` -> ``(title, full markdown)``."""
    global _index
    if _index is not None:
        return _index

    index: dict[str, tuple[str, str]] = {}
    for path in sorted(DOCS_DIR.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"MCP docs: skipping unreadable page {path}: {exc}")
            continue
        relpath = path.relative_to(DOCS_DIR).as_posix()
        index[relpath] = (_title_of(text, relpath), text)

    logger.info(f"MCP docs: indexed {len(index)} pages from {DOCS_DIR}")
    _index = index
    return _index


def _term_index() -> dict[str, tuple[Counter, int, set[str]]]:
    """Per page: body word counts, body length in words, and the words of title and path."""
    global _terms
    if _terms is None:
        _terms = {}
        for relpath, (title, text) in _load_index().items():
            body = _words(text)
            _terms[relpath] = (Counter(body), len(body), set(_words(f"{title} {relpath.removesuffix('.md')}")))
    return _terms


def _resolve(path: str) -> str | None:
    """Normalize a caller-supplied page path to an indexed key.

    Returns None when the page does not exist. Raises ValueError if the path
    tries to escape DOCS_DIR — this is a trust boundary, callers are untrusted.
    """
    candidate = path.strip().lstrip("/")
    if not candidate:
        return None
    if not candidate.endswith(".md"):
        candidate = f"{candidate}.md"

    resolved = (DOCS_DIR / candidate).resolve()
    if DOCS_DIR not in resolved.parents:
        raise ValueError(f"Path outside documentation tree: {path}")

    key = resolved.relative_to(DOCS_DIR).as_posix()
    return key if key in _load_index() else None


def _snippet(text: str, term: str) -> str:
    """~300 chars of body text centred on the first hit for ``term``."""
    pos = text.lower().find(term)
    if pos == -1:
        pos = 0
    start = max(0, pos - MAX_SNIPPET_CHARS // 2)
    end = min(len(text), start + MAX_SNIPPET_CHARS)
    body = re.sub(r"\s+", " ", text[start:end]).strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{body}{suffix}"


mcp = MCPServer(
    name="livekit-api-docs",
    title="LiveKit Agents API Documentation",
    instructions=(
        "Documentation for the LiveKit Agents voice-AI REST API: assistants, "
        "outbound/inbound calls, SIP trunks, tools, audio library, analytics, "
        "webhooks, releases, migrations, compatibility, usage accounting, and "
        "container deployment. Call search_docs with the user's question, then "
        "get_doc on the most specific API or reference page. Use changelog.md for "
        "release and breaking-change context. Answer only from what these tools "
        "return — never guess endpoint paths, field names, model IDs, defaults, "
        "prices, provider capabilities, or deployment-specific facts. State when "
        "a field is nullable, a value is versioned, or a cost is only an estimate."
    ),
    version=__version__,
)


@mcp.tool()
def list_docs() -> str:
    """List every documentation page as a table of contents.

    Returns each page's path (use it with get_doc) and title, grouped by
    section. Use this to orient yourself; prefer search_docs when you already
    know what you are looking for.
    """
    index = _load_index()
    groups: dict[str, list[str]] = {}
    for relpath, (title, _) in index.items():
        section = relpath.split("/")[0] if "/" in relpath else "(root)"
        groups.setdefault(section, []).append(f"  {relpath} — {title}")

    lines = [f"{len(index)} pages:"]
    for section in sorted(groups):
        lines.append(f"\n## {section}")
        lines.extend(groups[section])
    return "\n".join(lines)


@mcp.tool()
def get_doc(path: str) -> str:
    """Read one documentation page as raw markdown.

    Args:
        path: Page path relative to the docs root, e.g. "api/calls/trigger.md".
            The ".md" suffix is optional. Get valid paths from list_docs or
            search_docs.
    """
    try:
        key = _resolve(path)
    except ValueError as exc:
        return str(exc)

    if key is None:
        return f"No page at '{path}'. Call list_docs or search_docs for valid paths."

    title, text = _load_index()[key]
    return f"<!-- {key} — {title} -->\n{text}"


@mcp.tool()
def search_docs(query: str, limit: int = 8) -> str:
    """Search all documentation pages for keywords and return the best matches.

    Ranks pages with BM25: a word counts for more when few pages use it, repeating it helps
    less and less, long pages are discounted, and a word in the page title or path counts extra.
    Returns path, title and a short snippet per hit — follow up with get_doc to read a
    promising page in full.

    Args:
        query: Words to look for, e.g. "trigger outbound call payload".
        limit: Maximum number of pages to return (default 8).
    """
    terms = list(dict.fromkeys(_words(query)))
    if not terms:
        return "Empty query. Pass some keywords."

    pages = _term_index()
    if not pages:
        return "No documentation pages are indexed."
    avg_len = max(1.0, sum(length for _, length, _ in pages.values()) / len(pages))
    rarity = {}
    for term in terms:
        df = sum(1 for counts, _, title in pages.values() if counts[term] or term in title)
        rarity[term] = math.log(1 + (len(pages) - df + 0.5) / (df + 0.5))

    scored: list[tuple[float, str]] = []
    for relpath, (counts, length, title) in pages.items():
        norm = BM25_K1 * (1 - BM25_B + BM25_B * length / avg_len)
        score = 0.0
        for term in terms:
            tf = counts[term]
            score += rarity[term] * tf * (BM25_K1 + 1) / (tf + norm)
            if term in title:
                score += TITLE_BOOST * rarity[term]
        if score:
            scored.append((score, relpath))

    if not scored:
        return f"No pages match '{query}'. Try fewer or broader keywords, or call list_docs."

    scored.sort(key=lambda row: (-row[0], row[1]))
    index = _load_index()
    limit = max(1, limit)
    lines = [f"{len(scored)} matches, top {min(limit, len(scored))}:"]
    for score, relpath in scored[:limit]:
        title, text = index[relpath]
        hit = next((t for t in terms if t in text.lower()), terms[0])
        lines.append(f"\n### {title}\npath: {relpath} (score {score:.2f})\n{_snippet(text, hit)}")
    return "\n".join(lines)


# host="0.0.0.0" opts out of the localhost-only DNS-rebinding defaults, which
# would otherwise reject the production Host header.
_starlette_app = mcp.streamable_http_app(
    streamable_http_path="/mcp",
    stateless_http=True,
    host="0.0.0.0",
)

# The bare streamable-HTTP ASGI handler. The server attaches it as an exact
# "/mcp" route rather than app.mount(), because mounting makes Starlette answer
# "/mcp" with a 307 to "/mcp/" and not every MCP client follows redirects.
asgi_app = _starlette_app.routes[0].app
