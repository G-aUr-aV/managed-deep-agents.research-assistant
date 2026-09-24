"""Search scholarly papers through the OpenAlex Works API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

from langchain.tools import tool

_API_URL = "https://api.openalex.org/works"
_USER_AGENT = "research-assistant/0.0.0 (paper_search)"
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

#: Abstract budget per paper. The abstract is what the model uses to judge
#: relevance and to describe what a paper found, so cutting it defeats the
#: search. Structured abstracts in medicine and the Nature journals run past
#: 2000 characters; this clears them while keeping a full 25-result page under
#: the harness's 80k-char tool-result ceiling.
_ABSTRACT_CHARS = 2500

_SORTS: dict[str, str] = {
    "relevance": "relevance_score:desc",
    "newest": "publication_date:desc",
}


def _request_json(params: dict[str, Any]) -> dict[str, Any]:
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
    text = " ".join(word for _, word in sorted(words))
    if len(text) <= _ABSTRACT_CHARS:
        return text
    return f"{text[:_ABSTRACT_CHARS]}… [truncated]"


def _normalize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    locations = [
        location
        for location in paper.get("locations") or []
        if isinstance(location, dict)
    ]
    published_locations = [
        location
        for location in locations
        if "preprint" not in str(location.get("raw_type", "")).lower()
    ]
    # A preprint-only record still has a citable DOI. Report the DOI either way
    # and flag the preprint case so the model can say so rather than silently
    # citing an OpenAlex work id.
    preprint_only = not published_locations and bool(locations)
    ranked = published_locations or locations
    best_location = next(
        (
            location
            for location in ranked
            if location.get("is_oa") and location.get("landing_page_url")
        ),
        ranked[0] if ranked else {},
    )
    open_access = paper.get("open_access") or {}
    doi = paper.get("doi") or ""

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
        "cited_by_count": paper.get("cited_by_count"),
        "venue": (
            (best_location.get("source") or {}).get("display_name", "")
            if isinstance(best_location.get("source"), dict)
            else ""
        ),
        "url": doi or best_location.get("landing_page_url") or paper.get("id", ""),
        "doi": doi,
        "preprint_only": preprint_only,
        "open_access_pdf": (
            best_location.get("pdf_url") or open_access.get("oa_url") or ""
        ),
    }


@tool(parse_docstring=True)
def paper_search(
    query: str,
    max_results: int = 5,
    sort: Literal["relevance", "newest"] = "relevance",
    from_year: int | None = None,
    to_year: int | None = None,
    min_citations: int | None = None,
    open_access_only: bool = False,
) -> dict[str, Any]:
    """Search scholarly papers using OpenAlex.

    Returns titles, authors, dates, DOIs, citation counts, and truncated
    abstracts. Use `fetch_page` on a DOI or open-access PDF URL to read a paper
    before citing its numbers or conclusions.

    Args:
        query: Plain-text terms describing the paper or research topic.
        max_results: Maximum number of papers to return (1-25).
        sort: `newest` for the current state of a fast-moving field, else
            `relevance`. There is no citation sort: ranking by citation count
            ignores the query and returns whatever is most cited overall.
        from_year: Only include papers published in or after this year.
        to_year: Only include papers published in or before this year.
        min_citations: Drop papers cited fewer than this many times. Use this
            rather than a citation sort to bias toward established work, and
            keep it low or unset for work published in the last year or two.
        open_access_only: Only include papers with a free full text.
    """
    limit = max(1, min(int(max_results), 25))
    filters: list[str] = []
    if from_year is not None:
        filters.append(f"from_publication_date:{int(from_year)}-01-01")
    if to_year is not None:
        filters.append(f"to_publication_date:{int(to_year)}-12-31")
    if min_citations is not None:
        filters.append(f"cited_by_count:>{max(0, int(min_citations) - 1)}")
    if open_access_only:
        filters.append("is_oa:true")

    params: dict[str, Any] = {
        "search": query,
        "per-page": limit,
        "sort": _SORTS.get(sort, _SORTS["relevance"]),
        "select": (
            "id,title,authorships,publication_year,publication_date,doi,"
            "cited_by_count,open_access,locations,ids,abstract_inverted_index"
        ),
    }
    if filters:
        params["filter"] = ",".join(filters)

    try:
        payload = _request_json(params)
    except Exception as exc:  # noqa: BLE001 — return errors to the model
        return {"query": query, "results": [], "error": str(exc)}

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
