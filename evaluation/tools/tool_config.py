"""Centralized tool configuration.

Defaults come from environment variables. CLI args in each benchmark can
override these. The endpoint / key defaults below are placeholders — set
``SEARCH_API_ENDPOINT`` / ``SEARCH_API_KEY`` / ``FETCH_API_ENDPOINT`` /
``FETCH_API_KEY`` to point at a real web-search / fetch service before running
the BrowseComp pipeline.
"""

from __future__ import annotations

import os


def get_search_config() -> dict:
    return {
        "endpoint": os.environ.get("SEARCH_API_ENDPOINT", "http://web-api.local:8081"),
        "api_key": os.environ.get("SEARCH_API_KEY", "replace-with-your-web-api-key"),
        "max_retry": 3,
        "timeout": 120.0,
    }


def get_fetch_config() -> dict:
    return {
        "endpoint": os.environ.get("FETCH_API_ENDPOINT", "http://web-api.local:8081"),
        "api_key": os.environ.get("FETCH_API_KEY", "replace-with-your-web-api-key"),
        "timeout": 300.0,
        "max_retry": 3,
        "max_page_length": 10000,
        "use_cache": True,
    }
