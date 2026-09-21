---
name: research
description: Multi-source research workflow — outline questions, search the web and scholarly papers, take notes, and return a cited brief.
---

Use this skill for questions that need sources, comparison, or a written brief. Skip it for greetings and one-fact lookups the user already specified.

## Procedure

1. If the request is vague, follow the `qa` skill first (one question at a time, at most three). Do not search until the goal is clear enough to outline.
2. Write a short outline of 2–5 research questions.
3. Search with `internet_search` for web sources and `paper_search` when the topic is scientific, technical, or likely to have papers. Run more than one query if the first results are thin.
4. Keep a compact claim/source ledger in the current conversation: claims,
   quotes, and the URL or DOI for each. Do not assume filesystem or shell
   tools are available.
5. Read `/memories/agent/` if this topic may have been researched before. After a useful brief, add a compact topic note and source list there — never PII, credentials, or customer records.
6. Apply the `citation-hygiene` skill before drafting the final answer.
7. Return a concise cited brief to the user:
   - Lead with the answer, not the process.
   - Every non-trivial claim has a citation (URL and/or DOI).
   - Separate well-supported findings from open questions or weak sources.
   - Do not invent papers, quotes, or URLs.
