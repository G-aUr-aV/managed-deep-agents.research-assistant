"""Retrieve current, targeted library documentation from Context7."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from langchain.tools import tool

_BASE_URL = "https://context7.com"
_USER_AGENT = "research-assistant/0.0.0 (context7_docs)"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _request_json(
    path: str,
    params: dict[str, str],
    api_key: str,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{_BASE_URL}{path}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": _USER_AGENT,
        },
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read())
                if not isinstance(payload, dict):
                    raise RuntimeError("Context7 returned a non-object response")
                return payload
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUS_CODES or attempt == 1:
                try:
                    details = json.loads(exc.read()).get("message", exc.reason)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    details = exc.reason
                raise RuntimeError(f"Context7 API HTTP {exc.code}: {details}") from exc
            retry_after = exc.headers.get("Retry-After", "1")
            try:
                time.sleep(min(float(retry_after), 4.0))
            except ValueError:
                time.sleep(1.0)
        except urllib.error.URLError as exc:
            if attempt == 1:
                raise RuntimeError(f"Context7 API request failed: {exc.reason}") from exc
            time.sleep(1.0)

    raise RuntimeError("Context7 API request failed")


def _versioned_library_id(library_id: str, version: str | None) -> str:
    if not version or "@" in library_id:
        return library_id
    return f"{library_id.rstrip('/')}/{version.lstrip('/')}"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_context(payload: dict[str, Any], max_chars: int) -> dict[str, Any]:
    code_snippets: list[dict[str, str]] = []
    remaining = max_chars
    for snippet in payload.get("codeSnippets") or []:
        if not isinstance(snippet, dict) or remaining <= 0:
            continue
        title = _text(snippet.get("codeTitle"))
        code_parts: list[str] = []
        for code_item in snippet.get("codeList") or []:
            if isinstance(code_item, dict):
                code = _text(code_item.get("code"))
            else:
                code = _text(code_item)
            if code:
                code_parts.append(code)
        code = "\n\n".join(code_parts)
        if not code:
            continue
        clipped = code[:remaining]
        code_snippets.append({"title": title, "code": clipped})
        remaining -= len(clipped)

    info_snippets: list[str] = []
    for snippet in payload.get("infoSnippets") or []:
        if remaining <= 0:
            break
        if isinstance(snippet, dict):
            content = _text(snippet.get("content"))
        else:
            content = _text(snippet)
        if content:
            clipped = content[:remaining]
            info_snippets.append(clipped)
            remaining -= len(clipped)

    return {
        "code_snippets": code_snippets,
        "info_snippets": info_snippets,
        "truncated": remaining <= 0,
    }


@tool(parse_docstring=True)
def context7_docs(
    library: str,
    query: str,
    version: str | None = None,
) -> dict[str, Any]:
    """Find a library and retrieve focused, version-aware documentation from Context7.

    Args:
        library: Library or framework name, such as "LangChain" or "FastAPI".
        query: Specific documentation question, including the desired API or task.
        version: Optional library version to pin when Context7 supports it.
    """
    api_key = os.getenv("CONTEXT7_API_KEY")
    if not api_key:
        return {
            "library": library,
            "query": query,
            "results": [],
            "error": "CONTEXT7_API_KEY is not set",
        }

    try:
        search = _request_json(
            "/api/v2/libs/search",
            {"libraryName": library, "query": query},
            api_key,
        )
        matches = [
            item for item in search.get("results") or [] if isinstance(item, dict)
        ]
        if not matches:
            return {
                "library": library,
                "query": query,
                "results": [],
                "error": "Context7 could not resolve the library",
            }

        selected = matches[0]
        library_id = _text(selected.get("id"))
        if not library_id:
            raise RuntimeError("Context7 returned a library without an id")
        library_id = _versioned_library_id(library_id, version)

        context = _request_json(
            "/api/v2/context",
            {
                "libraryId": library_id,
                "query": query,
                "type": "json",
            },
            api_key,
        )
        normalized = _normalize_context(context, max_chars=16000)
        return {
            "library": library,
            "query": query,
            "library_id": library_id,
            "library_url": f"{_BASE_URL}{library_id}",
            "matched_library": {
                "title": selected.get("title", ""),
                "description": selected.get("description", ""),
                "version": selected.get("version", ""),
            },
            **normalized,
        }
    except Exception as exc:  # noqa: BLE001 — return errors to the model
        return {"library": library, "query": query, "results": [], "error": str(exc)}
