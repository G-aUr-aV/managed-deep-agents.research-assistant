"""Read the text of a specific page so claims can be checked at the source."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlparse

from langchain.tools import tool

from tools._tavily import clip, tavily_client

#: Text budget for the whole call, shared across the pages it returns.
#:
#: Sized just under the harness's own ceiling: `FilesystemMiddleware` offloads
#: any tool result over `tool_token_limit_before_evict` (20k tokens = 80k chars)
#: to a file and hands the model a preview plus a path. That is a good fallback
#: but a worse default — an offloaded result costs an extra `read_file` round
#: trip and takes the text out of the model's direct view while it is reasoning
#: about the claim. Staying under the threshold keeps a normal fetch inline and
#: quotable; anything genuinely larger still degrades to the offload path.
_CALL_CHARS = 60000

#: Pages per call. Extract is billed per URL and the model reasons better over
#: a handful of pages it actually read than over a large batch it skimmed.
_MAX_URLS = 5


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


@tool(parse_docstring=True)
def fetch_page(
    urls: list[str],
    query: str | None = None,
    extract_depth: Literal["basic", "advanced"] = "basic",
) -> dict[str, Any]:
    """Fetch the readable text of specific web pages by URL.

    Use this to verify a claim against its source instead of citing a search
    snippet: quantitative claims, dates, versions, quotations, and anything
    current or disputed. Pass URLs returned by `internet_search` or
    `paper_search`, or URLs the user supplied.

    Args:
        urls: Absolute http(s) URLs to read (1-5 per call).
        query: Optional focus so long pages are chunked around what matters.
        extract_depth: `advanced` for pages that render poorly (PDFs, JS-heavy
            sites); it is slower and costs more.
    """
    candidates = [url for url in urls if _is_http_url(url)][:_MAX_URLS]
    rejected = [url for url in urls if not _is_http_url(url)]
    if not candidates:
        return {
            "pages": [],
            "failed": rejected,
            "error": "No absolute http(s) URL was supplied",
        }

    try:
        payload = tavily_client().extract(
            urls=candidates,
            extract_depth=extract_depth,
            format="markdown",
            query=query,
            include_images=False,
        )
    except Exception as exc:  # noqa: BLE001 — return errors to the model
        return {"pages": [], "failed": candidates + rejected, "error": str(exc)}

    items = [item for item in payload.get("results") or [] if isinstance(item, dict)]
    pages: list[dict[str, Any]] = []
    remaining = _CALL_CHARS
    for index, item in enumerate(items):
        # Even split of what is left, so a short page hands its unused budget to
        # the pages after it and a single-URL fetch gets the whole allowance.
        share = remaining // (len(items) - index)
        raw = item.get("raw_content")
        raw = raw.strip() if isinstance(raw, str) else ""
        truncated = len(raw) > share
        text = f"{raw[:share]}… [truncated]" if truncated else raw
        remaining -= len(raw[:share])
        pages.append(
            {
                "url": item.get("url", ""),
                "title": clip(item.get("title"), 300),
                "text": text,
                "truncated": truncated,
                **(
                    {
                        "note": (
                            "Only the first part of this page is shown. Fetch it "
                            "again with a `query` to pull the passages that answer "
                            "your question instead of the top of the document."
                        )
                    }
                    if truncated
                    else {}
                ),
            }
        )

    failed = [
        item.get("url", "") if isinstance(item, dict) else str(item)
        for item in payload.get("failed_results") or []
    ]
    return {"pages": pages, "failed": failed + rejected}
