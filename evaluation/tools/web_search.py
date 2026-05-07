"""Web search tool — async wrapper around a Google-search HTTP API.

Protocol follows the external deepagent-test search service:
  POST {endpoint}/search  with Bearer auth.
"""

from __future__ import annotations

import asyncio
import logging
import random

import aiohttp

logger = logging.getLogger(__name__)

MAX_QUERIES = 3
MAX_RETRY = 3


async def search(
    queries: list[str],
    endpoint: str,
    api_key: str,
    *,
    num: int = 10,
    timeout: float = 120.0,
) -> str:
    """Run 1-3 web searches and return a formatted result string."""
    if isinstance(queries, str):
        queries = [queries]
    if not queries:
        return "Error: queries required"

    prefix = ""
    if len(queries) > MAX_QUERIES:
        prefix = (
            f"This tool only supports {MAX_QUERIES} queries at most. "
            f"Results of the first {MAX_QUERIES} queries are returned.\n\n"
        )
        queries = queries[:MAX_QUERIES]

    results = await asyncio.gather(
        *[_search_one(q, num, endpoint, api_key, timeout) for q in queries]
    )

    return prefix + _format(queries, results)


async def _search_one(
    query: str,
    num: int,
    endpoint: str,
    api_key: str,
    timeout: float,
) -> list[dict]:
    url = f"{endpoint.rstrip('/')}/search"
    payload = {
        "query": query,
        "num": num,
        "extendParams": {
            "country": "us",
            "locale": "en",
            "location": "United States",
            "page": 1,
            "type": "search",
        },
        "platformInput": {"model": "google-search"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    for attempt in range(MAX_RETRY):
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
            return data["data"]["originalOutput"]["organic"]
        except Exception as e:
            if attempt == MAX_RETRY - 1:
                logger.error("Search failed for '%s' after %d attempts: %s",
                             query, MAX_RETRY, e)
                return []
            await asyncio.sleep(random.uniform(1, 2))
    return []


def _format(queries: list[str], results: list[list[dict]]) -> str:
    parts: list[str] = []
    for query, items in zip(queries, results):
        parts.append(f"Search results for '{query}':")
        if not items:
            parts.append("No results found\n")
            continue
        for i, item in enumerate(items, 1):
            title = item.get("title", "No title")
            url = item.get("link", item.get("url", "No URL"))
            date = item.get("date", "")
            snippet = (
                item.get("snippet", item.get("Snippet", "No snippet"))
                .replace("\xa0", " ")
            )
            line = f"{i}. {title}\n   URL: {url}\n"
            if date:
                line += f"   Date: {date}\n"
            line += f"   Snippet: {snippet}\n"
            parts.append(line)
    return "\n".join(parts).strip()
