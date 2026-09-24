"""Shared, lazily-initialized Tavily client.

Constructed on first use rather than at import time: a missing
``TAVILY_API_KEY`` should surface as a tool-level error the model can report,
not as an ``ImportError`` that stops the whole agent from compiling.
"""

from __future__ import annotations

import os
import threading

from tavily import TavilyClient

_client: TavilyClient | None = None
_lock = threading.Lock()


class MissingTavilyKeyError(RuntimeError):
    """Raised when ``TAVILY_API_KEY`` is absent."""


def tavily_client() -> TavilyClient:
    """Return the process-wide Tavily client, creating it on first call."""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is None:
            api_key = os.getenv("TAVILY_API_KEY")
            if not api_key:
                raise MissingTavilyKeyError("TAVILY_API_KEY is not set")
            _client = TavilyClient(api_key=api_key)
    return _client


def clip(value: object, limit: int) -> str:
    """Return ``value`` as text, truncated to ``limit`` characters."""
    text = value.strip() if isinstance(value, str) else ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… [truncated]"
