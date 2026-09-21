"""Search scholarly papers through the OpenAlex Works API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from langchain.tools import tool

_API_URL = "https://api.openalex.org/works"
_USER_AGENT = "research-assistant/0.0.0 (paper_search)"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _request_json(query: str, limit: int) -> dict[str, Any]:
    params: dict[str, Any] = {
        "search": query,
        "per-page": limit,
        "select": (
            "id,title,authorships,publication_year,publication_date,doi,"
            "open_access,locations,ids,abstract_inverted_index"
        ),
    }
    email = os.getenv("OPENALEX_EMAIL")
    if email:
        params["mailto"] = email

    request = urllib.request.Request(
        f"{_API_URL}?{urllib.parse.urlencode(params)}",
        headers={
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )

    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUS_CODES or attempt == 1:
                raise RuntimeError(
                    f"OpenAlex API HTTP {exc.code} {exc.reason}".strip()
                ) from exc
            time.sleep(2.0)
        except urllib.error.URLError as exc:
            if attempt == 1:
                raise RuntimeError(
                    f"OpenAlex API request failed: {exc.reason}"
                ) from exc
            time.sleep(1.0)

    raise RuntimeError("OpenAlex API request failed")


def _abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        words.extend((position, word) for position in positions)
    return " ".join(word for _, word in sorted(words))


def _normalize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    locations = [
        location
        for location in paper.get("locations") or []
        if isinstance(location, dict)
    ]
    non_preprint_locations = [
        location
        for location in locations
        if "preprint" not in str(location.get("raw_type", "")).lower()
    ]
    best_location = next(
        (
            location
            for location in non_preprint_locations
            if location.get("is_oa") and location.get("landing_page_url")
        ),
        non_preprint_locations[0] if non_preprint_locations else {},
    )
    open_access = paper.get("open_access") or {}
    doi = (paper.get("doi") or "") if non_preprint_locations else ""

    return {
        "paper_id": paper.get("id", ""),
        "title": paper.get("title") or "",
        "abstract": _abstract(paper.get("abstract_inverted_index")),
        "authors": [
            (author.get("author") or {}).get("display_name", "")
            for author in paper.get("authorships") or []
            if (author.get("author") or {}).get("display_name")
        ],
        "year": paper.get("publication_year"),
        "publication_date": paper.get("publication_date") or "",
        "url": doi or best_location.get("landing_page_url") or paper.get("id", ""),
        "doi": doi,
        "open_access_pdf": (
            best_location.get("pdf_url")
            or (open_access.get("oa_url") if non_preprint_locations else "")
            or ""
        ),
    }


@tool(parse_docstring=True)
def paper_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search scholarly papers using OpenAlex.

    Args:
        query: Plain-text terms describing the paper or research topic.
        max_results: Maximum number of papers to return (1-25).
    """
    limit = max(1, min(int(max_results), 25))
    try:
        payload = _request_json(query, limit)
        papers = [
            _normalize_paper(paper)
            for paper in payload.get("results", [])
            if isinstance(paper, dict)
        ]
        return {
            "query": query,
            "total": (payload.get("meta") or {}).get("count"),
            "results": papers,
        }
    except Exception as exc:  # noqa: BLE001 — return errors to the model
        return {"query": query, "results": [], "error": str(exc)}
