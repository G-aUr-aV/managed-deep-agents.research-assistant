"""Make skill loading, evidence gathering, and citation honesty deterministic.

`deepagents` mounts skills with *progressive disclosure*: the model is shown
each skill's name and description and is trusted to `read_file` the matching
`SKILL.md` when it applies. That is a prompt-level suggestion, so a smaller or
faster model complies only some of the time — the same reason a rule in
`instructions.md` gets skipped.

This middleware turns the suggestion into a checked precondition. It runs
inside `wrap_model_call`, so it can inspect a draft answer *before* that answer
is committed to graph state and, when a requirement is unmet, re-ask the model
with a corrective instruction. Three requirements are enforced:

1. **Skill loaded.** The `SKILL.md` for the workflow this request maps to must
   have been read in the current turn.
2. **Evidence gathered.** At least one research tool must have run before an
   answer that depends on external facts.
3. **Citations real.** Every URL in an external-research answer must appear in
   a tool result from this turn. A URL the model composed itself is the single most
   damaging failure mode for a research assistant, and it is cheap to catch.

Corrections are appended to the *request* only. They never enter graph state,
so the thread the user sees carries no retry scaffolding, and a rejected draft
is discarded rather than shown. When a requirement is still unmet after
`max_retries`, the last draft is returned rather than failing the turn — the
gate is a strong nudge with a bounded cost, not a hard block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ContextT,
    ModelRequest,
    ModelResponse,
    ResponseT,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence


@dataclass(frozen=True)
class SkillRule:
    """Map a class of request onto what the agent must do before answering it.

    Rules are evaluated in order and the first match wins, so declare the
    narrowest rule first and end with a catch-all (`patterns=()`).

    Attributes:
        name: Label for this request class, used in log-free diagnostics only.
        patterns: Case-insensitive regexes; any match selects this rule. An
            empty tuple always matches, making the rule a catch-all.
        skills: Directory names of skills whose `SKILL.md` must be read before
            answering. Empty means this class of request needs no workflow.
        require_evidence: Whether an answer must be preceded by a research
            tool call. Turn this off for rules that summarize the existing
            conversation rather than the outside world.
    """

    name: str
    patterns: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    require_evidence: bool = True

    def matches(self, request_text: str) -> bool:
        """Whether this rule claims ``request_text``."""
        if not self.patterns:
            return True
        return any(
            re.search(pattern, request_text, re.IGNORECASE) for pattern in self.patterns
        )


#: Source scope matters more than topic keywords: saved notes about a paper
#: are not a request for a new literature search. Do not make memory reads
#: count as external evidence; mixed requests must still gather fresh evidence.
_LOCAL_SOURCE = (
    r"\b(?:from|in|using|based on|according to|check|read|fetch|retrieve|search|"
    r"recall|summari[sz]e|summari[sz]ing|summar[yi]es? of)\s+(?:only\s+)?"
    r"(?:(?:the|my|our|your|saved|stored|durable|existing|agent)\s+)*"
    r"(?:memor(?:y|ies)|notes)\b",
    r"/memories/",
    r"\b(?:saved|stored|durable) (?:memor(?:y|ies)|notes)\b",
    r"\b(?:what|which)\b.{0,40}\b(?:remember|saved|stored)\b",
    r"\b(?:our|this|the) (?:conversation|chat|thread|discussion|previous answer)\b",
    r"\b(?:attached|uploaded|pasted|provided|supplied)\b",
    r"\b(?:from|using|based on|according to)\s+(?:this|that|these|those|my|our)\s+"
    r"(?:text|code|data|notes|document|file|table|passage|transcript|premises)\b",
    r"\b(?:text|code|data|notes|document|file|table|passage|transcript|answer) "
    r"(?:above|below)\b",
    r"\b(?:summari[sz]e|rewrite|translate|reformat|explain|extract|analyze)\s+"
    r"(?:the\s+)?(?:above|below|following)\b",
    r"\b(?:text|code|data|notes|document|file|table|passage|transcript) "
    r"(?:I|we|you) (?:provided|shared|pasted|uploaded)\b",
)

_LOCAL_TASKS = (
    r"^\s*(hi|hey|hello|yo|thanks|thank you|thx|ok|okay|got it|cool|nice|"
    r"sure|no|yes|yep|nope|stop|cancel|never ?mind)\b[\s!.?]*$",
    r"\b(?:what did (?:you|we|I)|you just said|repeat that|say that again)\b",
    r"\b(?:summari[sz]e|recap|rephrase|rewrite|reword|proofread|copy ?edit|"
    r"shorten|expand|translate|reformat|explain|extract|organize|sort|convert|debug|solve|"
    r"tidy up|clean up)\s+(?:this|that|it|these|those)\b",
    r"^\s*(?:please\s+)?(?:summari[sz]e|recap|rephrase|shorten|continue)\s*[.!?]*$",
    r"\b(?:rewrite|reword|proofread|copy ?edit|shorten|translate|reformat)\b"
    r".{0,40}\b(?:my|the following)\b",
    r"^\s*(?:please\s+)?(?:list|extract)\s+(?:(?:the|all|any)\s+)?"
    r"(?:key (?:points|decisions)|action items|takeaways)\b",
    r"\b(?:make|put|turn)\b.{0,30}\b(?:this|that|it)\b.{0,30}\b"
    r"(?:table|bullets|bullet points|JSON|CSV)\b",
    r"\b(?:write|compose|invent)\b.{0,40}\b(?:poem|fictional|story|haiku|joke)\b",
    r"\bbrainstorm\b.{0,40}\b(?:names|titles|slogans|fictional)\b",
    r"^\s*(?:please\s+)?(?:calculate|compute|simplify|solve|evaluate)\s+"
    r"(?:[\d\s+x*/%().=^−-]|\bof\b)+[.!?]*$",
    r"^\s*(?:what is|what's)\s+[\d\s+x*/%().=^−-]+[?!.]*$",
)

# Explicit requests for new evidence override local tasks. Bare topic words
# ("news", "paper", "latest") do not: they may describe supplied material.
_EXPLICIT_EXTERNAL = (
    r"\b(?:search|browse)\s+(?:(?:the|on)\s+)*(?:web|internet|online)\b",
    r"\b(?:internet_search|paper_search|context7_docs|fetch_page)\b",
    r"\b(?:fact[- ]?check|verify)\b",
    r"\b(?:online|externally|on the web|on the internet)\b",
)

_NEW_EVIDENCE = (
    r"\b(?:find|fetch|check|use|include|add|with|using|against|get|update|refresh|compare\s+with)\b"
    r".{0,40}\b(?:latest|current|up[- ]to[- ]date|new|recent|live|external|online)\b",
    r"\b(?:find|search\s+for|cite|add)\b.{0,40}\b(?:sources|citations|papers|studies)\b",
)

_LOOKUP_REQUEST = (
    r"(?:^|\b(?:please|you|to))\s*(?:look\s+up|research|investigate)\b",
)

_NO_RESEARCH = (
    r"\b(?:do not|don't|don’t|no need to|without)\s+(?:search(?:ing)?|brows(?:e|ing)|"
    r"look(?:ing)?\s+up|us(?:e|ing)\s+(?:any\s+)?(?:external|outside)\s+sources)\b",
    r"\b(?:no|without)\s+(?:web\s+search|browsing|external\s+sources|outside\s+sources)\b",
    r"\b(?:use|using|from)\s+(?:only\s+)?(?:your\s+)?(?:own\s+)?"
    r"(?:memory|existing knowledge|general knowledge|training data)\s+only\b",
)


def _matches(patterns: Sequence[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _request_parts(text: str) -> list[str]:
    """Separate instructions from clearly delimited material to transform.

    Do not classify words inside quotations/code as requests. A following or
    below block belongs to the transformation; a bare URL still needs fetching.
    This is intentionally conservative, not a general natural-language parser.
    """
    def unquote(match: re.Match[str]) -> str:
        quoted = match.group().strip('`"“” ')
        # A quoted URL/path is still a source reference, not its contents.
        return quoted if re.match(r"^(?:https?://|/memories/)\S+$", quoted) else ""

    text = re.sub(r'```.*?```|`[^`]*`|"[^"\n]*"|“[^”]*”', unquote, text, flags=re.DOTALL)
    payload = re.search(r"\b(?:following|below)\b[^:\n]*[:\n]", text, re.IGNORECASE)
    if payload and not re.match(r"\s*https?://", text[payload.end():]):
        text = text[:payload.end()]
    elif ":" in text:
        instruction, supplied = text.split(":", 1)
        if (_matches(_LOCAL_TASKS, instruction)
                and re.search(r"\b(?:summari[sz]e|rewrite|translate|rephrase|reformat)\b",
                              instruction, re.IGNORECASE)
                and not re.match(r"\s*https?://", supplied)):
            text = instruction
    return [part.strip() for part in re.split(
        r"[;\n]|[.!?](?:\s+|$)|\b(?:and then|and|then|but|also)\s+"
        r"(?=(?:please |can you |could you )?(?:summari[sz]e|recap|rewrite|"
        r"rephrase|translate|list|extract|make|put|turn|give|find|fetch|search|"
        r"browse|look|research|verify|fact-check|check|compare|include|add|"
        r"update|refresh|what|which|how|is|are)\b)", text,
        flags=re.IGNORECASE,
    ) if part.strip()]


def _needs_external(part: str) -> bool:
    if _matches(_NO_RESEARCH, part):
        return False
    if _matches(_EXPLICIT_EXTERNAL, part):
        return True
    local_source = _matches(_LOCAL_SOURCE, part)
    if _matches(_NEW_EVIDENCE, part):
        # 'Find current prices in saved notes' is still retrieval. Updating
        # those notes or comparing against current facts requires evidence.
        return not local_source or bool(re.search(
            r"\b(?:update|refresh|against|with|using|include|add)\b.{0,40}"
            r"\b(?:latest|current|new|recent|live|external)\b", part, re.IGNORECASE
        ))
    return _matches(_LOOKUP_REQUEST, part) and not local_source


def _is_self_contained(text: str) -> bool:
    """Exempt bounded local work while keeping unscoped questions gated.

    Classify each requested operation so 'summarize this and research X' does
    not inherit the summary's exemption. Unknown clauses keep the safe default.
    """
    parts = _request_parts(text)
    if not parts:
        return False
    no_research = any(_matches(_NO_RESEARCH, part) for part in parts)
    for part in parts:
        local_source = _matches(_LOCAL_SOURCE, part)
        # Negative search instructions are constraints, not lookup requests.
        if _matches(_NO_RESEARCH, part):
            continue
        if _needs_external(part):
            return False
        if no_research:
            continue
        # A URL alone is not supplied content, even with 'this' or 'below'.
        if re.search(r"https?://", part):
            return False
        if not (local_source or _matches(_LOCAL_TASKS, part)):
            return False
    return True


#: URLs extracted from a draft answer. Deliberately greedy about the path and
#: stops at whitespace or a closing bracket so Markdown links parse cleanly.
_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\)\]}]+")

_TRAILING_PUNCTUATION = ".,;:!?'\")]}>"


def _text_of(message: object) -> str:
    """Best-effort plain text for a message of any content shape."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(part for part in parts if isinstance(part, str))
    return str(content)


def _normalize_url(url: str) -> str:
    """Reduce a URL to a comparable host+path needle.

    Scheme, `www.`, trailing slash, trailing punctuation, and case are dropped
    so a URL quoted in prose still matches the same URL in a tool result.
    """
    needle = url.strip().rstrip(_TRAILING_PUNCTUATION).lower()
    for prefix in ("https://", "http://"):
        if needle.startswith(prefix):
            needle = needle[len(prefix) :]
    if needle.startswith("www."):
        needle = needle[4:]
    return needle.rstrip("/")


def _current_turn(messages: Sequence[Any]) -> list[Any]:
    """Messages belonging to the request being answered right now.

    Everything from the last human message onward. Earlier turns are excluded
    so a skill read three questions ago does not satisfy this question.
    """
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return list(messages[index:])
    return list(messages)


class _Turn:
    """What the model has actually done so far in the current turn."""

    def __init__(self, messages: Sequence[Any], evidence_tools: frozenset[str]) -> None:
        turn = _current_turn(messages)
        self.request_text = _text_of(turn[0]) if turn and isinstance(turn[0], HumanMessage) else ""
        self.read_paths: set[str] = set()
        self.evidence_calls = 0
        self.tool_result_text: list[str] = []

        for message in turn:
            if isinstance(message, AIMessage):
                for call in message.tool_calls or []:
                    name = call.get("name", "")
                    if name == "read_file":
                        path = (call.get("args") or {}).get("file_path")
                        if isinstance(path, str):
                            self.read_paths.add(path)
                    elif name in evidence_tools:
                        self.evidence_calls += 1
            elif isinstance(message, ToolMessage):
                self.tool_result_text.append(_text_of(message).lower())

    def has_read(self, skill_path: str) -> bool:
        """Whether ``skill_path`` was read in this turn."""
        return any(path.rstrip("/") == skill_path.rstrip("/") for path in self.read_paths)

    def cites(self, url: str) -> bool:
        """Whether ``url`` appears in any tool result from this turn."""
        needle = _normalize_url(url)
        if not needle:
            return False
        return any(needle in result for result in self.tool_result_text)


@dataclass
class _Requirements:
    """The preconditions a draft answer to this turn must satisfy."""

    skill_paths: list[str] = field(default_factory=list)
    require_evidence: bool = False

    @property
    def gated(self) -> bool:
        """Whether this turn is gated at all."""
        return bool(self.skill_paths) or self.require_evidence


class SkillGateMiddleware(AgentMiddleware[AgentState[Any], ContextT, ResponseT]):
    """Require the matching skill, real evidence, and real URLs before answering.

    Args:
        rules: Request classes and the skills they require, first match wins.
        evidence_tools: Tool names that count as gathering external evidence.
        skills_root: Mount point of the skills tree, used to build a
            `SKILL.md` path when the skills middleware has not populated
            `skills_metadata` in state.
        max_retries: How many times one model call may be re-asked before the
            draft is accepted as-is.
    """

    def __init__(
        self,
        *,
        rules: Sequence[SkillRule],
        evidence_tools: Sequence[str],
        skills_root: str = "/skills/",
        max_retries: int = 2,
    ) -> None:
        super().__init__()
        self.rules = tuple(rules)
        self.evidence_tools = frozenset(evidence_tools)
        self.skills_root = f"/{skills_root.strip('/')}/"
        self.max_retries = max(0, int(max_retries))

    # ------------------------------------------------------------------ hooks

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Brief the model on outstanding requirements, then check its draft."""
        requirements = self._requirements(request)
        attempt = self._brief(request, requirements)
        response = handler(attempt)
        for _ in range(self.max_retries):
            correction = self._correction(request, requirements, response)
            if correction is None:
                return response
            attempt = self._append(attempt, correction)
            response = handler(attempt)
        return response

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        """Async twin of :meth:`wrap_model_call`."""
        requirements = self._requirements(request)
        attempt = self._brief(request, requirements)
        response = await handler(attempt)
        for _ in range(self.max_retries):
            correction = self._correction(request, requirements, response)
            if correction is None:
                return response
            attempt = self._append(attempt, correction)
            response = await handler(attempt)
        return response

    # ------------------------------------------------------------- inspection

    def _requirements(self, request: ModelRequest[ContextT]) -> _Requirements:
        """Resolve which skills and evidence this turn demands."""
        turn = _Turn(request.messages, self.evidence_tools)
        text = turn.request_text.strip()
        if not text or _is_self_contained(text):
            return _Requirements()

        # A recap rule must not swallow an additional request for fresh facts.
        parts = _request_parts(text)
        external = any(
            _needs_external(part)
            or (
                not _is_self_contained(part)
                and not any(
                    not candidate.require_evidence and candidate.matches(part)
                    for candidate in self.rules
                )
            )
            for part in parts
        )
        rule = next(
            (candidate for candidate in self.rules
             if candidate.matches(text) and (candidate.require_evidence or not external)),
            None,
        )
        if rule is None:
            return _Requirements()

        return _Requirements(
            skill_paths=self._skill_paths(request, rule.skills),
            require_evidence=rule.require_evidence,
        )

    def _skill_paths(
        self, request: ModelRequest[ContextT], names: Sequence[str]
    ) -> list[str]:
        """Resolve skill names to `SKILL.md` paths, preferring live state.

        The skills middleware records the paths it actually mounted in
        `skills_metadata`; falling back to `<root>/<name>/SKILL.md` keeps the
        gate working when that state is absent (subagents, tests).
        """
        state = request.state or {}
        metadata = state.get("skills_metadata") or []
        known = {
            entry["name"]: entry["path"]
            for entry in metadata
            if isinstance(entry, dict) and entry.get("name") and entry.get("path")
        }
        return [known.get(name, f"{self.skills_root}{name}/SKILL.md") for name in names]

    def _correction(
        self,
        request: ModelRequest[ContextT],
        requirements: _Requirements,
        response: object,
    ) -> str | None:
        """The instruction to re-ask with, or `None` if the draft is acceptable."""
        if not requirements.gated:
            return None
        draft = _final_answer(response)
        if draft is None:
            # The model asked for a tool. Let the loop run; requirements are
            # only checked against an answer the user would actually receive.
            return None

        turn = _Turn(request.messages, self.evidence_tools)
        problems: list[str] = []

        unread = [path for path in requirements.skill_paths if not turn.has_read(path)]
        if unread:
            calls = "\n".join(
                f'  read_file(file_path="{path}", limit=1000)' for path in unread
            )
            problems.append(
                "You have not loaded the workflow required for this request. "
                f"Call these first, then follow what they say:\n{calls}"
            )

        if requirements.require_evidence and turn.evidence_calls == 0:
            problems.append(
                "You have not looked anything up. This request depends on facts "
                "that need external evidence. Gather evidence for that part "
                "of the request before answering: "
                f"{', '.join(sorted(self.evidence_tools))}."
            )

        invented = [
            url
            for url in dict.fromkeys(_URL_PATTERN.findall(_text_of(draft)))
            if requirements.require_evidence and not turn.cites(url)
        ]
        if invented:
            listed = "\n".join(f"  {url}" for url in invented[:10])
            problems.append(
                "These URLs in your draft do not appear in any tool result from "
                "this turn, so they are unverified and must not be presented as "
                f"citations:\n{listed}\n"
                "Either fetch them to confirm they exist and say what you claim, "
                "or remove them and cite a URL a tool actually returned."
            )

        if not problems:
            return None

        numbered = "\n\n".join(
            f"{index}. {problem}" for index, problem in enumerate(problems, start=1)
        )
        return (
            "[automated review — your draft answer was not sent to the user]\n\n"
            f"{numbered}\n\n"
            "Fix every point above, then answer. Do not restate this notice."
        )

    # ----------------------------------------------------------- request edits

    def _brief(
        self, request: ModelRequest[ContextT], requirements: _Requirements
    ) -> ModelRequest[ContextT]:
        """Append outstanding requirements to the system message.

        Stating the requirement before the call is what keeps the retry path
        rare; the retry exists for when this is ignored anyway. Satisfied
        requirements drop out, so the block disappears once the model complies.
        """
        if not requirements.gated:
            return request
        turn = _Turn(request.messages, self.evidence_tools)
        lines: list[str] = []
        for path in requirements.skill_paths:
            if not turn.has_read(path):
                lines.append(
                    f'- Not yet done: read_file(file_path="{path}", limit=1000) '
                    "— required before you answer."
                )
        if requirements.require_evidence and turn.evidence_calls == 0:
            lines.append(
                "- Not yet done: look this up with "
                f"{' or '.join(sorted(self.evidence_tools))} — required before you answer."
            )
        if not lines:
            return request

        block = (
            "\n\n## Required before answering this request\n\n"
            + "\n".join(lines)
        )
        if requirements.require_evidence:
            block += (
                "\n\nEvery URL you cite must come from a tool result in this turn. "
                "Do not write a URL you have not seen a tool return."
            )
        existing = request.system_message
        base = existing.text if isinstance(existing, SystemMessage) else ""
        return request.override(system_message=SystemMessage(content=f"{base}{block}"))

    def _append(
        self, request: ModelRequest[ContextT], correction: str
    ) -> ModelRequest[ContextT]:
        """Re-ask with ``correction`` appended to this request only."""
        return request.override(
            messages=[*request.messages, HumanMessage(content=correction)]
        )


def _final_answer(response: object) -> AIMessage | None:
    """The `AIMessage` a draft would send to the user, if this is one.

    A response carrying tool calls is mid-work, not an answer, so it is not
    subject to the gate.
    """
    if isinstance(response, AIMessage):
        message: AIMessage | None = response
    else:
        result = getattr(response, "result", None)
        if result is None:
            model_response = getattr(response, "model_response", None)
            result = getattr(model_response, "result", None)
        if not isinstance(result, list):
            return None
        message = next(
            (item for item in reversed(result) if isinstance(item, AIMessage)), None
        )
    if message is None or message.tool_calls:
        return None
    return message


__all__ = ["SkillGateMiddleware", "SkillRule"]
