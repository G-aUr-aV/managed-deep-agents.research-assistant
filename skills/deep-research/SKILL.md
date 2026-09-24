---
name: deep-research
description: Run a rigorous investigation for complex, ambiguous, or high-impact questions using decomposition, source triangulation, evidence tracking, and explicit uncertainty.
---

# Deep research

Use this skill instead of the lighter `research` workflow when the question
has several dependent parts, competing explanations, important decisions,
conflicting evidence, or a need for current and defensible conclusions. Do not
use it for greetings, simple lookups, or questions that one reliable source
can answer.

## 1. Scope the investigation

- Restate the decision or question in one sentence.
- Identify the date range, geography, population, definitions, and constraints
  that affect the answer.
- Break the question into three to seven concrete subquestions.
- Note what would count as sufficient evidence before searching.

If an unstated assumption could materially change the result, ask a clarifying
question or state the assumption explicitly.

## 2. Build a search plan

- Search each subquestion separately with more than one wording.
- Start with primary sources and authoritative datasets or papers.
- Use `internet_search` for current web sources, `paper_search` for scholarly
  literature, and `context7_docs` for library and framework APIs.
- `fetch_page` every source a conclusion rests on. At this level of rigor a
  search snippet is a lead, never evidence, and a source you have not read is
  a source you cannot characterize.
- Search for both supporting and contradicting evidence.
- Track publication dates and prefer the most recent authoritative source when
  the subject changes over time.

## 3. Maintain an evidence ledger

Keep a compact evidence ledger in the current conversation. For each important
source, record:

- the source title, publisher or authors, date, and direct URL or DOI;
- the specific claim or data it supports;
- important limitations, definitions, or population differences;
- whether it confirms, qualifies, or contradicts another source.

Do not treat search snippets, repeated reporting, or multiple pages copied from
one source as independent confirmation. Two outlets restating one press
release is one source.

## 4. Triangulate and resolve conflicts

- Cross-check important claims with at least two genuinely independent sources
  when feasible.
- Prefer the source closest to the original data or event when sources differ.
- Explain disagreements instead of averaging incompatible numbers.
- Check that differences are not caused by dates, units, samples, or
  definitions.
- Mark a conclusion as tentative when the evidence remains incomplete or
  conflicting.

Apply `citation-hygiene` while evaluating sources and before drafting. Never
invent a source, URL, quote, statistic, or level of certainty.

## 5. Stop and synthesize

Stop searching when each subquestion has adequate evidence, new searches only
repeat known sources, or the remaining gap cannot be resolved with available
evidence. Return:

1. A direct answer or recommendation.
2. The key findings organized by subquestion.
3. Important disagreements, limitations, and open questions.
4. A short methods or scope note only when it helps the reader judge the work.

Use `response-formatting` for the final structure. Put citations next to the
claims they support rather than producing an unexplained list of links.
