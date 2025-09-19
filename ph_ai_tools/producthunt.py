"""Helpers for scraping Product Hunt for AI tool listings."""
from __future__ import annotations

from dataclasses import dataclass, field
from html import unescape
import gzip
import json
from typing import Iterable, List, Optional, Sequence, Tuple
import urllib.error
import urllib.request

__all__ = [
    "AiTool",
    "ProductHuntScrapeError",
    "scrape_top_ai_tools",
    "fetch_topic_page",
]

PRODUCT_HUNT_BASE_URL = "https://www.producthunt.com"
DEFAULT_TOPIC_SLUG = "artificial-intelligence"
DEFAULT_LIMIT = 5
DEFAULT_TIMEOUT = 20


class ProductHuntScrapeError(RuntimeError):
    """Base exception raised when scraping Product Hunt fails."""


@dataclass(slots=True)
class AiTool:
    """Container describing an AI tool listing on Product Hunt."""

    name: str
    tagline: str
    makers: List[str] = field(default_factory=list)
    product_hunt_url: str = ""
    external_url: Optional[str] = None
    votes_count: Optional[int] = None

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation of the tool."""

        data = {
            "name": self.name,
            "tagline": self.tagline,
            "makers": self.makers,
            "product_hunt_url": self.product_hunt_url,
        }
        if self.external_url:
            data["external_url"] = self.external_url
        if self.votes_count is not None:
            data["votes_count"] = self.votes_count
        return data


def fetch_topic_page(topic_slug: str = DEFAULT_TOPIC_SLUG, *, timeout: int = DEFAULT_TIMEOUT) -> str:
    """Download the Product Hunt topic page HTML for the provided slug.

    Parameters
    ----------
    topic_slug:
        Product Hunt topic identifier (e.g. ``"artificial-intelligence"``).
    timeout:
        Timeout in seconds for the HTTP request.

    Returns
    -------
    str
        Raw HTML returned by Product Hunt.

    Raises
    ------
    ProductHuntScrapeError
        Raised if the page could not be downloaded.
    """

    url = f"{PRODUCT_HUNT_BASE_URL}/topics/{topic_slug}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProductHuntScraper/1.0; +https://www.producthunt.com/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Accept-Encoding": "gzip",
            "Connection": "close",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ProductHuntScrapeError(
                    f"Failed to fetch {url}: HTTP status {response.status}"
                )
            raw = response.read()
            encoding = response.headers.get("Content-Encoding", "").lower()
            if "gzip" in encoding:
                raw = gzip.decompress(raw)
            elif "br" in encoding:
                try:
                    import brotli  # type: ignore
                except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
                    raise ProductHuntScrapeError(
                        "Received Brotli encoded response but the 'brotli' package is not installed."
                    ) from exc
                raw = brotli.decompress(raw)
            return raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:  # pragma: no cover - requires network access
        raise ProductHuntScrapeError(
            f"Failed to fetch {url}: HTTP error {exc.code}"
        ) from exc
    except urllib.error.URLError as exc:  # pragma: no cover - requires network access
        raise ProductHuntScrapeError(
            f"Network error while fetching {url}: {exc.reason}"
        ) from exc


def scrape_top_ai_tools(
    *,
    topic_slug: str = DEFAULT_TOPIC_SLUG,
    limit: int = DEFAULT_LIMIT,
    html: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> List[AiTool]:
    """Scrape Product Hunt for the top AI tools within the provided topic.

    Parameters
    ----------
    topic_slug:
        Product Hunt topic identifier.
    limit:
        Maximum number of AI tools to return.
    html:
        Optional HTML payload. If provided, the function will parse the HTML
        instead of performing a network request. This is primarily intended for
        testing purposes.
    timeout:
        Timeout in seconds to use for network requests if ``html`` is not provided.

    Returns
    -------
    list of :class:`AiTool`
        Extracted AI tools ordered by vote count (when available).

    Raises
    ------
    ProductHuntScrapeError
        Raised if the Product Hunt payload did not contain any AI tool entries.
    """

    if limit <= 0:
        return []

    if html is None:
        html = fetch_topic_page(topic_slug, timeout=timeout)

    payload = _extract_next_data(html)
    indexed_tools = _extract_tools(payload)
    if not indexed_tools:
        raise ProductHuntScrapeError(
            "No AI tools were found in the Product Hunt payload."
        )
    ordered = sorted(
        indexed_tools,
        key=lambda item: (
            -(item[1].votes_count or 0),
            item[0],
        ),
    )
    return [tool for _, tool in ordered[:limit]]


def _extract_next_data(html: str) -> dict:
    """Extract the ``__NEXT_DATA__`` JSON object from Product Hunt HTML."""

    start_token = '<script id="__NEXT_DATA__" type="application/json">'
    start_index = html.find(start_token)
    if start_index == -1:
        raise ProductHuntScrapeError(
            "Could not locate __NEXT_DATA__ script tag within the HTML payload."
        )
    start_index += len(start_token)
    end_index = html.find("</script>", start_index)
    if end_index == -1:
        raise ProductHuntScrapeError(
            "Encountered malformed HTML when searching for __NEXT_DATA__ payload."
        )
    json_blob = unescape(html[start_index:end_index])
    try:
        return json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ProductHuntScrapeError(
            "Failed to decode Product Hunt JSON payload."
        ) from exc


def _extract_tools(payload: dict) -> List[Tuple[int, AiTool]]:
    """Walk the Product Hunt payload and collect post objects."""

    candidates: List[Tuple[int, AiTool]] = []
    seen_slugs: set[str] = set()
    order_counter = 0

    for node in _iter_nodes(payload):
        if not isinstance(node, dict):
            continue
        typename = node.get("__typename")
        if isinstance(typename, str):
            if "Post" not in typename and "Product" not in typename:
                continue
        else:
            continue
        slug = node.get("slug")
        name = node.get("name") or node.get("title")
        if not slug or not name:
            continue
        if slug in seen_slugs:
            continue
        tool = _build_tool(node, slug, str(name))
        if tool is None:
            continue
        seen_slugs.add(slug)
        candidates.append((order_counter, tool))
        order_counter += 1
    return candidates


def _build_tool(node: dict, slug: str, name: str) -> Optional[AiTool]:
    """Create an :class:`AiTool` from a Product Hunt node."""

    tagline = node.get("tagline") or node.get("description") or ""
    tagline = str(tagline).strip()

    makers = _extract_maker_names(node)

    product_hunt_url = node.get("profileUrl") or f"{PRODUCT_HUNT_BASE_URL}/posts/{slug}"

    external_url = (
        node.get("websiteUrl")
        or node.get("website")
        or node.get("redirectUrl")
        or node.get("url")
    )
    if not external_url and isinstance(node.get("urls"), dict):
        external_url = node["urls"].get("website")

    votes_count = _extract_votes(node)

    return AiTool(
        name=name.strip(),
        tagline=tagline,
        makers=makers,
        product_hunt_url=product_hunt_url,
        external_url=external_url,
        votes_count=votes_count,
    )


def _extract_votes(node: dict) -> Optional[int]:
    """Extract the vote count from a Product Hunt node."""

    raw_votes = node.get("votesCount") or node.get("votes")
    if isinstance(raw_votes, dict):
        raw_votes = raw_votes.get("count")
    if raw_votes is None:
        return None
    try:
        return int(raw_votes)
    except (TypeError, ValueError):
        return None


def _iter_nodes(payload: dict) -> Iterable[dict]:
    """Yield dictionaries from an arbitrarily nested structure."""

    stack: List[object] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _extract_maker_names(node: dict) -> List[str]:
    """Extract maker names from a Product Hunt node."""

    candidate_keys = [
        "makers",
        "makersPreview",
        "makersConnection",
        "primaryMaker",
        "primaryMakers",
        "maker",
        "team",
        "teamMembers",
    ]
    names: List[str] = []
    for key in candidate_keys:
        if key in node:
            names.extend(_normalise_people(node[key]))
    return _deduplicate(names)


def _normalise_people(value) -> List[str]:  # type: ignore[no-untyped-def]
    """Normalise different GraphQL user representations into plain names."""

    names: List[str] = []
    if value is None:
        return names
    if isinstance(value, list):
        for item in value:
            names.extend(_normalise_people(item))
        return names
    if isinstance(value, dict):
        if "displayName" in value or "name" in value:
            display_name = value.get("displayName") or value.get("name")
            if display_name:
                names.append(str(display_name))
        # GraphQL connections may expose ``nodes`` or ``edges`` collections.
        for key in ("nodes", "edges", "profiles", "items", "collection", "members"):
            if key in value:
                container = value[key]
                if key == "edges" and isinstance(container, list):
                    for edge in container:
                        if isinstance(edge, dict) and "node" in edge:
                            names.extend(_normalise_people(edge["node"]))
                        else:
                            names.extend(_normalise_people(edge))
                else:
                    names.extend(_normalise_people(container))
        if "node" in value and isinstance(value["node"], (dict, list)):
            names.extend(_normalise_people(value["node"]))
        if "user" in value:
            names.extend(_normalise_people(value["user"]))
        if "users" in value:
            names.extend(_normalise_people(value["users"]))
        return names
    return names


def _deduplicate(values: Sequence[str]) -> List[str]:
    """Deduplicate a sequence of strings while preserving order."""

    seen: set[str] = set()
    result: List[str] = []
    for item in values:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
