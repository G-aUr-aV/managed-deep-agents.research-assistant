"""Compile the research assistant.

`instructions.md` carries the always-on policy and `skills/**` the on-demand
workflows. Both are prompt-level, which a fast model follows only some of the
time, so the routing that must not be optional is enforced in middleware
instead — see `middleware/skill_gate.py`.
"""

import os

from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_openai import ChatOpenAI
from managed_deepagents import define_deep_agent

from middleware import SkillGateMiddleware, SkillRule
from tools.context7 import context7_docs
from tools.fetch import fetch_page
from tools.papers import paper_search
from tools.search import internet_search

#: Tool calls that count as having looked something up. `fetch_page` is
#: included because reading a page the user supplied is genuine evidence.
EVIDENCE_TOOLS = ("internet_search", "paper_search", "context7_docs", "fetch_page")

#: First match wins, so these run narrowest-first and end with a catch-all.
SKILL_RULES = (
    SkillRule(
        name="conversation-recap",
        patterns=(
            r"\bstand[- ]?up\b",
            r"\b(what did (we|i) (do|get done|cover|decide))\b",
            r"\b(progress|end of day) (summary|report|review)\b",
            r"\b(my|our) (day|week|work|progress) (summary|recap|review)\b",
            r"\bwhere (did|do) we (leave off|stand)\b",
        ),
        # Conversation progress does not require a current-events lookup.
        skills=("response-formatting",),
        require_evidence=False,
    ),
    SkillRule(
        name="daily-tech-brief",
        patterns=(
            r"\b(?:daily|today'?s|morning) (?:tech |technology )?(?:brief|summary|digest|recap|update)\b",
            r"\b(?:tech|technology) (?:news|brief|digest|headlines|updates?|recap)\b",
            r"\b(?:latest|recent) (?:tech|technology)\b",
            r"\bwhat(?:'s| has| is)? (?:happened|new) (?:recently|lately|today|in tech|in technology)\b",
            r"\bwhat(?:'s| is) new\b",
            r"\bwhat(?:'s| has)? happened in (?:AI|software|cybersecurity)\b",
            r"\b(?:latest|recent) (?:AI|software|cybersecurity) (?:news|updates?|headlines)\b",
            r"\b(?:news|headlines|current events) (?:today|recently|this week)\b",
        ),
        skills=("daily-tech-brief", "response-formatting"),
    ),
    SkillRule(
        name="deep-research",
        patterns=(
            r"\bdeep(-| )?(research|dive)\b",
            r"\b(comprehensive|exhaustive|rigorous|systematic|thorough)\b",
            r"\b(literature|evidence) review\b",
            r"\btrade[- ]?offs?\b",
            r"\b(pros and cons|for and against|competing|conflicting)\b",
            r"\b(landscape|state of the art|market survey)\b",
            r"\bwhich (one )?should (we|i)\b",
            r"\b(build vs\.? buy|migrate (from|to))\b",
        ),
        skills=("deep-research", "citation-hygiene", "response-formatting"),
    ),
    SkillRule(
        name="research-brief",
        patterns=(
            r"\bresearch\b",
            r"\b(brief|report|write[- ]?up|overview|summary) (on|of|about)\b",
            r"\bcompare\b",
            r"\b\w+ vs\.? \w+",
            r"\b(options|alternatives|approaches|benchmarks?)\b",
            r"\b(papers?|studies|literature|citations?)\b",
            # Several questions in one turn is a brief, not a lookup.
            r"\?[^?]*\?",
        ),
        skills=("research", "citation-hygiene", "response-formatting"),
    ),
    SkillRule(
        name="lookup",
        # Catch-all: a single-fact question still has to be looked up and
        # formatted, but it does not need a multi-step research workflow.
        skills=("response-formatting",),
    ),
)

model = ChatOpenAI(
    model=os.environ["DEEPINFRA_MODEL"],
    base_url="https://api.deepinfra.com/v1",
    api_key=os.environ["DEEPINFRA_API_KEY"],
)

agent = define_deep_agent(
    name="research-assistant-preview",
    model=model,
    tools=[internet_search, paper_search, context7_docs, fetch_page],
    middleware=[
        SkillGateMiddleware(
            rules=SKILL_RULES,
            evidence_tools=EVIDENCE_TOOLS,
            max_retries=2,
        ),
        # Backstop against a research loop that will not converge. This counts
        # model *nodes*, not API calls: a gate retry re-asks inside one node and
        # is not counted here, so the real ceiling is this limit times the
        # gate's own retry budget.
        ModelCallLimitMiddleware(run_limit=40, exit_behavior="end"),
    ],
)
