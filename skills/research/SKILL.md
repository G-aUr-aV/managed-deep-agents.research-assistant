---
name: research
description: Multi-source research workflow — outline questions, search the web and scholarly papers, take notes, and return a cited brief.
---

Use this skill for questions that need sources, comparison, or a written brief. Skip it for greetings and one-fact lookups the user already specified.

## Procedure

1. If the request is vague, follow the `qa` skill first (one question at a time, at most three). Do not search until the goal is clear enough to outline.
2. Write a short outline of 2–5 research questions.
3. Search with `internet_search` for web sources, `paper_search` when the topic is scientific, technical, or likely to have papers, and `context7_docs` for library and framework APIs. Run more than one query if the first results are thin.
4. `fetch_page` the sources that carry your important claims. A snippet is
   enough to decide a page is worth reading; it is not enough to cite for a
   number, a date, a version, or a quotation.
5. Keep a compact claim/source ledger in the current conversation: the claim,
   the supporting quote or figure, and the URL or DOI it came from. Every URL
   in the ledger must be one a tool returned.
6. Read `/memories/agent/` if this topic may have been researched before. After a useful brief, add a compact topic note, its source list, and the date — never PII, credentials, or customer records.
7. Apply the `citation-hygiene` skill before drafting the final answer.
8. Return a concise cited brief to the user:
   - Lead with the answer, not the process.
   - Every non-trivial claim has a citation (URL and/or DOI).
   - Separate well-supported findings from open questions or weak sources.
   - Do not invent papers, quotes, or URLs.
