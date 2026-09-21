---
name: response-formatting
description: Format substantive user-facing answers for clarity, scanability, and appropriate citation placement.
---

# Response formatting

Use this skill for any answer longer than a short paragraph, any answer with
multiple steps, or any answer that includes research findings, code, errors, or
file changes.

## Default rules

- Lead with the answer, outcome, or diagnosis. Do not lead with the process.
- Use plain Markdown with short paragraphs and descriptive headings only when
  they improve navigation.
- Put a blank line before every list. Keep list items parallel and concise.
- Prefer one useful structure over several competing structures.
- Avoid repeating the user's question or narrating internal reasoning.
- Keep the answer proportional to the request. Include necessary caveats, but
  omit background that does not help the user act.

## Choose the structure by task

- A direct question: answer in one or two paragraphs, then add a brief caveat
  only if it changes the conclusion.
- Instructions or a procedure: use numbered steps and include commands in
  fenced code blocks with a language tag when applicable.
- A diagnosis: state the cause first, then show the relevant evidence, fix, and
  verification command.
- A comparison or repeated mapping: use a compact table. Do not use a table
  for a simple sequence or a paragraph of prose.
- Research or sourced claims: use a short conclusion, organized findings, and
  citations immediately after the claims they support. Never invent a source or
  citation.
- Code or configuration changes: summarize the result first, link to relevant
  files, and include only the smallest useful snippet.
- Errors and logs: quote only the important line, explain it in plain language,
  and provide the next actionable command.

## Final pass

Before sending, check that:

1. The first sentence gives the user the main result.
2. Headings and lists make the answer easier to scan rather than longer.
3. Commands are copyable and filenames are unambiguous.
4. Citations and links are placed next to the claims they support.
5. The response ends with a clear next step only when one is needed.
