---
name: daily-recap
description: Summarize the day's research, decisions, completed work, open threads, and next actions from available conversation, notes, and memory.
---

# Daily recap

Use this skill when the user asks for a daily recap, day summary, progress
summary, or a review of what happened during a time period. This skill creates
an on-demand recap; it does not schedule or send messages by itself.

## Establish the scope

- Use the user's local date and timezone when known.
- If the user gives a different date range, follow it explicitly.
- Review the current conversation and relevant durable memory when available.
- Do not claim that an event happened merely because it is absent from the
  notes. Say when the available record is incomplete.

## Build the recap

Organize the useful signal into these sections, omitting empty sections:

1. **Summary** — one or two sentences describing the day's main outcome.
2. **Completed** — concrete work finished, grouped by topic.
3. **Key findings or decisions** — facts learned and decisions made, with
   citations when they came from research.
4. **Open items** — unresolved questions, blockers, or follow-ups.
5. **Next actions** — specific, practical actions and their owner when known.

Include timestamps or links only when they help the user verify or continue the
work. Prefer concise bullets over a chronological transcript. Distinguish
completed work from proposed next steps.

## Accuracy and privacy

- Do not invent activity, progress, decisions, deadlines, or ownership.
- Preserve uncertainty and mention conflicting or incomplete information.
- Apply `citation-hygiene` to sourced findings and `response-formatting` to the
  final answer.
- Never expose credentials, tokens, private memory contents, or unrelated
  personal information in the recap.
- If there was no meaningful activity, say so directly instead of padding the
  recap.
