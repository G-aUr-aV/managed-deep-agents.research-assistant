"""Search the web through Tavily."""

from __future__ import annotations

from typing import Any, Literal

from langchain.tools import tool

from tools._tavily import clip, tavily_client

#: Per-result snippet budget. Snippets are leads — `fetch_page` is what reads a
#: source properly — so this only needs to be long enough to judge whether a
#: result is worth opening. `search_depth="advanced"` returns longer extracts;
#: this clears them without letting a 10-result page dominate the context.
_SNIPPET_CHARS = 2500

#: Upper bound on results. More than this rarely adds distinct sources and
#: makes the claim-to-source ledger harder for the model to keep straight.
_MAX_RESULTS = 10


def _normalize(result: object) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    url = result.get("url")
    if not isinstance(url, str) or not url:
        return None
    return {
        "title": clip(result.get("title"), 300),
        "url": url,
        "snippet": clip(result.get("content"), _SNIPPET_CHARS),
        "published_date": clip(result.get("published_date"), 40),
        "score": result.get("score"),
    }


@tool(parse_docstring=True)
def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    search_depth: Literal["basic", "advanced"] = "basic",
    time_range: Literal["day", "week", "month", "year"] | None = None,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Search the web for sources. Returns ranked snippets, not full pages.

    Snippets are leads. Use `fetch_page` on a result URL before treating its
    content as evidence for a quantitative, current, or disputed claim.

    Args:
        query: Search terms. Prefer several focused queries over one broad one.
        max_results: Number of results to return (1-10).
        topic: `news` for recent events, `finance` for markets, else `general`.
        search_depth: `advanced` costs more and digs deeper into each page.
        time_range: Restrict to the last day, week, month, or year.
        include_domains: Only return results from these domains.
        exclude_domains: Drop results from these domains.
    """
    limit = max(1, min(int(max_results), _MAX_RESULTS))
    try:
        payload = tavily_client().search(
            query,
            max_results=limit,
            topic=topic,
            search_depth=search_depth,
            time_range=time_range,
            include_domains=include_domains or None,
            exclude_domains=exclude_domains or None,
            include_answer=False,
            include_images=False,
            include_raw_content=False,
        )
    except Exception as exc:  # noqa: BLE001 — return errors to the model
        return {"query": query, "results": [], "error": str(exc)}

    results = [
        normalized
        for normalized in (_normalize(item) for item in payload.get("results") or [])
        if normalized is not None
    ]
    return {"query": query, "results": results}
