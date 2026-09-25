---
name: daily-tech-brief
description: Give an on-demand, sourced brief of recent technology news when the user asks what's happened recently, what's new in tech, or for a daily tech summary, digest, or recap.
---

# Daily tech brief

Use this skill for a current-events briefing about technology. A broad request
such as “what's happened recently?” means recent tech news in this assistant.
Follow a topic or time range the user specifies. This is an on-demand answer;
the skill does not schedule or send a briefing.

## Find the news

- Establish the current date and the user's timezone when available. For an
  unspecified daily brief, cover roughly the past 24 hours. For a general
  “recently” request, start with the past few days. State the period covered.
- Search with `internet_search(topic="news", time_range="day" or "week")`
  using several focused queries across relevant areas, such as AI, software,
  security, devices, major companies, and tech policy. Narrow to the user's
  requested topic when there is one. Expand the search window if the first
  pass has too little verified news, and tell the user when you do.
- Select developments for significance and relevance, not search rank. Avoid
  multiple entries for the same story, routine speculation, and old events
  that merely received a new article today.
- Check both when a source was published and when the underlying event
  happened. `fetch_page` the sources behind the selected claims. Prefer
  first-party announcements and primary documents; use credible reporting
  when it adds independent confirmation or the primary source is unavailable.

## Write the brief

- Lead with the most consequential developments. For each item, say what
  happened, when, and why it matters in plain language. Link a source directly
  beside the claim it supports.
- Distinguish announcements, shipped changes, reports, and unconfirmed claims.
  Flag material uncertainty or conflicting accounts.
- Keep it scannable and proportional to the request. If there is little
  verified news in the requested period, say so instead of padding the brief.
- Do not invent dates, facts, quotes, or URLs, and do not treat a search snippet
  as confirmation of a current claim.
