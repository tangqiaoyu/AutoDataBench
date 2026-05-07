"""Fetch tool — async web page retrieval via a Firecrawl-compatible API.

Fetches a URL, splits the content into pages, and returns the requested
page.  A ``FetchSession`` caches per-URL pages so repeated fetches of the
same URL (with increasing page numbers) don't hit the API again.
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

MAX_RETRY = 3
DEFAULT_PAGE_LENGTH = 10000  # chars per page (matches external _split_text_with_char default)


class FetchSession:
    """Per-rollout fetch cache.  Create one per ``arollout`` call."""

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        *,
        timeout: float = 300.0,
        max_page_length: int = DEFAULT_PAGE_LENGTH,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        if not self._endpoint.endswith("/fetch"):
            self._endpoint += "/fetch"
        self._api_key = api_key
        self._timeout = timeout
        self._max_page_length = max_page_length
        self._cache: dict[str, dict] = {}   # url → {title, pages}

    async def fetch(self, url: str, page: int = 1) -> str:
        if not url:
            return "Error: url required"

        if url not in self._cache:
            result = await self._fetch_url(url)
            if result is None:
                return f"Failed to fetch {url}"
            content = result.get("content", "")
            title = result.get("title", "")
            pages = _split_pages(content, self._max_page_length)
            self._cache[url] = {"title": title, "pages": pages}

        cached = self._cache[url]
        pages = cached["pages"]
        title = cached["title"] or "No title"

        if page < 1 or page > len(pages):
            return f"Page {page} does not exist. Available pages: 1-{len(pages)}"

        return _format_page(url, title, pages, page)

    async def _fetch_url(self, url: str) -> dict | None:
        payload = {
            "url": url,
            "onlyMainContent": True,
            "formats": ["markdown"],
            "maxAge": 172800000,
            "storeInCache": True,
            "timeout": int(self._timeout * 1000),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client_timeout = aiohttp.ClientTimeout(total=self._timeout)

        for attempt in range(MAX_RETRY):
            try:
                async with aiohttp.ClientSession(timeout=client_timeout) as session:
                    async with session.post(
                        self._endpoint, json=payload, headers=headers,
                    ) as resp:
                        result = await resp.json()

                if not result.get("success", False):
                    if attempt == MAX_RETRY - 1:
                        logger.error("Fetch API error for %s: %s", url, result)
                        return None
                    await asyncio.sleep(1)
                    continue

                data = result.get("data", {})
                metadata = data.get("metadata", {})
                content = data.get("markdown", data.get("html", ""))
                return {"content": content, "title": metadata.get("title", "")}

            except Exception as e:
                if attempt == MAX_RETRY - 1:
                    logger.error("Fetch failed for %s: %s", url, e)
                    return None
                await asyncio.sleep(1)

        return None


# ── page splitting ───────────────────────────────────────────────────────

def _split_pages(text: str, target_length: int,
                 search_range: int = 500) -> list[str]:
    """Split text into pages at paragraph/line boundaries."""
    if len(text) <= target_length:
        return [text] if text else [""]

    segments: list[str] = []
    start = 0
    while start < len(text):
        end = start + target_length
        if end >= len(text):
            segments.append(text[start:])
            break

        search_start = max(start, end - search_range)
        search_end = min(len(text), end + search_range)

        best = None
        for i in range(search_end - 1, search_start - 1, -1):
            if i + 1 < len(text) and text[i : i + 2] == "\n\n":
                best = i + 2
                break
        if best is None:
            for i in range(search_end - 1, search_start - 1, -1):
                if text[i] == "\n":
                    best = i + 1
                    break
        if best is None:
            best = end

        seg = text[start:best].strip()
        if seg:
            segments.append(seg)
        start = best

    return segments or [""]


def _format_page(url: str, title: str, pages: list[str], page: int) -> str:
    if len(pages) == 1:
        return (
            f"Fetched content from {url}:\n"
            f"Title: {title}\n"
            f"Content: {pages[0]}\n"
        )
    is_last = page == len(pages)
    return (
        f"Fetched content from {url}:\n"
        f"Title: {title}\n"
        f"The page is too long and has been split into {len(pages)} pages.\n"
        f"Page {page} Content: {pages[page - 1]}\n\n"
        f"Page {page} end."
        + ("" if is_last else " If you need more content, please fetch the next page.")
        + "\n"
    )
