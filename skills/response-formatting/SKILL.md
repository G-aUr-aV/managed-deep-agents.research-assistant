---
name: response-formatting
description: Format every user-facing answer for clarity, proportion, scanability, and appropriate citation placement.
---

# Response formatting

Use this skill for every user-facing answer, including a single-fact lookup,
conversation recap, news brief, research report, or short reply. Apply the
same standards at the scale the answer needs; a short answer may need only
one sentence.

## Default rules

- Lead with the answer, outcome, or diagnosis. Do not lead with the process.
- Match the requested format and level of detail when the user specifies them.
- Use plain Markdown with short paragraphs and descriptive headings only when
  they improve navigation.
- Put a blank line before every list. Keep list items parallel and concise.
- Prefer one useful structure over several competing structures.
- Avoid repeating the user's question or narrating internal reasoning.
- Keep the answer proportional to the request. Include necessary caveats, but
  omit background that does not help the user act.
- Keep simple replies simple; do not add a heading, list, table, or source
  section solely to satisfy a template.

## Choose the structure by task

- A direct question: answer in one or two paragraphs, then add a brief caveat
  only if it changes the conclusion.
- A conversation recap: summarize the key decisions, progress, and next steps
  in the order most useful to the user. Do not cite the conversation as an
  external source.
- A news brief: state the period covered, lead with the most consequential
  items, and put each source beside the development it supports.
- Instructions or a procedure: use numbered steps and include commands in
  fenced code blocks with a language tag when applicable.
- A diagnosis: state the cause first, then show the relevant evidence, fix, and
  verification command.
- A comparison or repeated mapping: use a compact table. Do not use a table
  for a simple sequence or a paragraph of prose.
- Research or sourced claims: use a short conclusion, organized findings, and
  citations immediately after the claims they support. Distinguish established
  findings from inferences or open questions. Never invent a source or citation.
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
5. The format matches the user's request and the answer's length.
6. The response ends with a clear next step only when one is needed.
